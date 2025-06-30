from flask import Flask, request, Response
from uuid import uuid4
import subprocess
import zipfile
import jinja2
import signal
import socket
import sys
import os
import re


SAFETY_CPU_SUBTRAHEND = 2
SAFETY_MEM_SUBTRAHEND = 1600
SAFE_SCHEDULING = os.getenv("SAFE_SCHEDULING", "False").strip().lower() == "true"

token_path = os.path.join(os.getcwd(), "results.token")
enso_file_path = os.path.join(os.getcwd(), ".ensorc")
custom_script_file_path = os.path.join(os.getcwd(), "run.sh")

PID = os.getpid()
try:
    SCRIPT_PATH = sys._MEIPASS
except AttributeError:
    SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
POD_IP = socket.gethostbyname(socket.gethostname())
OK = False


def template_values(token, pod_ip, file_data, cpu_num, cpu_requests, mem, memory_requests, replica_num, aditional_params, custom_script_file_data):
    jinja2_template = jinja2.Environment(loader=jinja2.FileSystemLoader(SCRIPT_PATH)).get_template("values.tpl.yaml")
    values_data = jinja2_template.render(token=token, pod_ip=pod_ip, file=file_data,
                                         cpu_num=cpu_num, cpu_requests=cpu_requests, mem=mem, mem_requests=memory_requests,
                                         replica_num=replica_num, additional_params=aditional_params,
                                         shm=os.getenv("ORCA_SHARED_MEMORY_ENABLED", "true"),
                                         shm_size=os.getenv("ORCA_SHARED_MEMORY_SIZE", "2Gi"), custom_script=custom_script_file_data)

    with open(os.path.join(SCRIPT_PATH, "values.yaml"), "w") as f:
        f.write(values_data)


def get_cpu_data():
    res = subprocess.run(
        "kubectl top -l openmpi-capable=true nodes  | tail -n +2 | tr -d 'm%' | awk '{print int($2 * (100 / $3 - 1) / 1000) - 2}'",
        capture_output=True, shell=True)
    cpus = [max(int(x), 1) for x in res.stdout.decode("utf-8").split("\n") if x != ""]
    return cpus


def get_available_cpu_data():
    res = subprocess.run(["/bin/bash", "-c", "paste -d' ' <(kubectl describe nodes -l openmpi-capable=true | grep -A11 \"Allocated resources\" | grep -A10 \"\\----\" | grep -v \"\\---\" | grep cpu | awk '{gsub(\"m\",\"\");print $2/1000}') <(kubectl get nodes -l openmpi-capable=true -o jsonpath='{.items[*].status.allocatable.cpu}' | sed \"s/ /\\n/g\") | awk '{printf \"%dm\\n\", ($2-$1)*1000}'"], capture_output=True, shell=False)
    cpus = [str(max(int(x[:-1]), 550))+x[-1:] for x in res.stdout.decode("utf-8").split("\n") if x != ""]
    return cpus


def get_mem_data():
    res = subprocess.run(
        "kubectl top -l openmpi-capable=true nodes  | tail -n +2 | tr -d 'm%' | awk '{printf \"%dMi\\n\", int($4 * (100 / $5 - 1)) - 4000}'",
        capture_output=True, shell=True)
    mem = [str(max(int(x[:-2]), 1000))+x[-2:] for x in res.stdout.decode("utf-8").split("\n") if x != ""]
    return mem


def get_available_mem_data():
    res = subprocess.run(["/bin/bash", "-c", "paste -d' ' <(kubectl describe nodes -l openmpi-capable=true | grep -A11 \"Allocated resources\" | grep -A10 \"\\----\" | grep -v \"\\---\" | grep memory | awk '{gsub(\"Mi\",\"\");print $2}') <(kubectl get nodes -l openmpi-capable=true -o jsonpath='{.items[*].status.allocatable.memory}' | sed \"s/ /\\n/g\" | awk '{gsub(\"Ki\",\"\");print $1/1000}') | awk '{printf \"%dMi\\n\", $2-$1}'"], capture_output=True, shell=False)
    mem = [str(max(int(x[:-2]), 2512))+x[-2:] for x in res.stdout.decode("utf-8").split("\n") if x != ""]
    return mem


def cleanup():
    print("cleaning up...")
    res = subprocess.run(
        f"helm template orca-executor {os.path.join(SCRIPT_PATH, 'charts', 'openmpi-cluster')} {f'--set extraFiles[0].path=/opt/enso/config --set-file extraFiles[0].file={enso_file_path}' if os.path.isfile(enso_file_path) else ''} -f {os.path.join(SCRIPT_PATH, 'values.yaml')} | kubectl delete -f -",
        capture_output=True, shell=True)
    os.remove(token_path)
    if res.returncode != 0:
        print(res.stderr.decode("utf-8"))
        return Response("Error cleaning up", status=400)
    print("Finished cleaning!")


if len(sys.argv) < 2:
    print("Required .inp file to run!")
    print("Use --help or -h flag to see help.")
    sys.exit(1)

if "--help" in sys.argv or "-h" in sys.argv:
    print("\nTakes .inp file and any set of args to pass to orca function.\n")
    print("If .inp file contains entry 'nprocs 0' it will be replaced")
    print("          with number of available processes automatically.\n")
    print("If .inp file contains entry 'maxcore 0' it will be replaced")
    print("              with calculated memory per core automatically.\n")
    print("Use 'orca-executor show nproc' to see available cpus in cluster.\n")
    print("Use 'orca-executor show logs' to see orca logs.\n")
    print("Use environment variable ORCA_NODES to overwrite number of worker nodes,")
    print("                                       useful for one node computations.\n")
    print("Use environment variable SAFE_SCHEDULING to enforce using maximum guaranteed cpus and memory instead of maximum potentially available, useful to avoid crashes due to resource over-scheduling, possible values: true/false, default: false.\n")
    print("Use environment variable ORCA_SHARED_MEMORY_ENABLED to mount external volume for shared memory,")
    print("                    useful if you run out of memory, possible values: true/false, default: true.\n")
    print("Use environment variable ORCA_SHARED_MEMORY_SIZE to set shared memory size if enabled,")
    print("                         possible values: XGi/XMi/XKi, where X - integer, default: 2Gi.\n")
    print("Use 'orca-executor exit' to finish orca gracefully.\n")
    print("\nTo run custom calculations, e.g. enso, place your bash code in run.sh file.\n")
    print("ORCA fullpath can be obtained with the command \"`echo $PATH | awk 'BEGIN{FS=\":\"; OFS=\"\\n\"} {$1=$1} 1' | grep orca | head -n 1`/orca\".\n")
    print("\nFor running enso calculations place .ensorc file in the same directory with following config:\n")
    print("""#NMR data
reference for 1H: TMS                      # ('TMS',)
reference for 13C: TMS                     # ('TMS',)
reference for 19F: CFCl3                   # ('CFCl3',)
reference for 31P: TMP                     # ('TMP', 'PH3')
reference for 29Si: TMS                    # ('TMS',)
1H active: on                              # ('on', 'off')
13C active: off                            # ('on', 'off')
19F active: off                            # ('on', 'off')
31P active: off                            # ('on', 'off')
29Si active: off                           # ('on', 'off')
resonance frequency: None                  # MHz number of your experimental spectrometer
nconf: all                                 # ('all', 'number e.g. 10')
charge: 0                                  # number e.g. 0
unpaired: 0                                # number e.g. 0
solvent: gas                               # (acetone, acetonitrile, chcl3, ch2cl2, dmso, h2o, methanol, thf, toluene, gas)
prog: None                                 # ('tm', 'orca')
ancopt: on                                 # ('on', 'off')
prog_rrho: xtb                             # ('xtb', 'prog', 'off')
gfn_version: gfn2                          # ('gfn1', 'gfn2')
temperature: 298.15                        # temperature in K e.g. 298.15
prog3: prog                                # ('tm', 'orca', 'prog')
prog4: prog                                # ('tm', 'orca', 'prog')
part1: on                                  # ('on', 'off')
part2: on                                  # ('on', 'off')
part3: on                                  # ('on', 'off')
part4: on                                  # ('on', 'off')
boltzmann: off                             # ('on', 'off')
backup: off                                # ('on', 'off')
func: pbeh-3c                              # ('pbeh-3c', 'b97-3c', 'tpss')
func3: pw6b95                              # ('pw6b95', 'wb97x', 'dsd-blyp')
basis3: def2-TZVPP                         # (several basis sets are possible)
funcJ: pbe0                                # ('tpss', 'pbe0')
basisJ: def2-TZVP                          # (several basis sets are possible)
funcS: pbe0                                # ('tpss', 'pbe0', 'dsd-blyp')
basisS: def2-TZVP                          # (several basis sets are possible)
couplings: on                              # ('on', 'off')
shieldings: on                             # ('on', 'off')
part1_threshold: 4.0                       # number e.g. 4.0
part2_threshold: 2.0                       # number e.g. 2.0
sm: default                                # ('cosmo', 'dcosmors', 'cpcm', 'smd')
smgsolv2: sm                               # ('sm', 'cosmors', 'gbsa_gsolv')
sm3: default                               # ('cosmors', 'smd', 'gbsa_gsolv')
sm4: default                               # ('cosmo', 'cpcm', 'smd')
check: on                                  # ('on', 'off')
crestcheck: off                            # ('on', 'off')
maxthreads: 0                              # number e.g. 2
omp: 0                                     # number e.g. 4\n""")
    sys.exit(0)

if sys.argv[1] == "exit":
    res = subprocess.run(
        "kubectl exec orca-executor-openmpi-cluster-0 -- bash -c 'ps -aux | grep \"`echo $PATH | awk '\"'\"'BEGIN{FS=\":\"; OFS=\"\\n\"} {$1=$1} 1'\"'\"' | grep orca | head -n 1`/orca results.inp\" | awk '\"'\"'{print $2}'\"'\"' | head -n-1 | xargs -I {} kill -9 {}'",
        capture_output=True, shell=True)
    if res.returncode != 0:
        print("Failed to terminate, perhaps not running?")
        print(res.stderr.decode("utf-8"))
        sys.exit(1)
    else:
        res = subprocess.run(
            "kubectl exec orca-executor-openmpi-cluster-0 -- bash -c 'ps -aux | grep \"tee\" | awk '\"'\"'{print $2}'\"'\"' | head -n-1 | xargs -I {} kill -9 {}'",
            capture_output=True, shell=True)
        res = subprocess.run(
            "kubectl exec orca-executor-openmpi-cluster-0 -- bash -c 'ps -aux | grep \"tee\" | awk '\"'\"'{print $2}'\"'\"' | head -n-1 | xargs -I {} kill -9 {}'",
            capture_output=True, shell=True)
        print("Graceful shutdown initiated.")
        sys.exit(0)

if sys.argv[1] == "show":
    if len(sys.argv) > 2:
        if sys.argv[2] == "nproc":
            cpus = get_cpu_data()
            if SAFE_SCHEDULING:
                s_cpus = list(map(lambda x: int(x[:-1])//1000, get_available_cpu_data()))
                print(min(s_cpus) * len(s_cpus))
            else:
                print(min(cpus) * len(cpus) - SAFETY_CPU_SUBTRAHEND)
            sys.exit(0)
        elif sys.argv[2] == "logs":
            res = subprocess.run(
                "kubectl logs orca-executor-openmpi-cluster-0",
                capture_output=True, shell=True)
            if res.returncode != 0:
                print("Failed to get logs, perhaps not running?")
                print(res.stderr.decode("utf-8"))
                sys.exit(1)
            else:
                print(res.stdout.decode("utf-8"))
                with open("tmp.out", 'w') as f:
                    f.write(res.stdout.decode("utf-8"))
                sys.exit(0)
        else:
            print("\nUnknown option")
            print("Use 'orca-executor show nproc' to see available cpus in cluster")
            print("Use 'orca-executor show logs' to see orca logs.")
            sys.exit(1)
    else:
        print("\nUse 'orca-executor show nproc' to see available cpus in cluster")
        print("Use 'orca-executor show logs' to see orca logs.")
        sys.exit(0)


app = Flask(__name__)


@app.route('/upload', methods=['POST'])
def upload():
    auth = request.headers.get("X-Api-Key")
    if app.config['AUTH_TOKEN'] != auth:
        return Response("Wrong auth token", status=401)

    with open(app.config['UPLOAD_FILE'], 'wb') as f:
        chunk_size = 4096
        while True:
            chunk = request.stream.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)

    with zipfile.ZipFile(app.config['UPLOAD_FILE'], 'r') as zip_ref:
        zip_ref.extractall(os.path.dirname(app.config['UPLOAD_FILE']))

    os.remove(app.config['UPLOAD_FILE'])

    cleanup()

    global OK
    OK = True
    pid = os.getpid()
    assert pid == PID
    os.kill(pid, signal.SIGINT)

    return Response("File uploaded successfully", status=200)


def run_app():
    app.run(host='0.0.0.0', port=8888)
    if not OK:
        print("Error occurred!")
        cleanup()


app.config['UPLOAD_FILE'] = os.path.join(os.getcwd(), "results.zip")

if os.path.exists(token_path):
    with open(token_path, 'r') as f:
        app.config['AUTH_TOKEN'] = f.read().replace("\n", "")
    print("Calculations already running! Waiting for the result.")
    template_values(app.config['AUTH_TOKEN'], "127.0.0.1", "Hello world!", "2", "1", "2500Mi", "2000Mi", 1, "", '')
    run_app()
    sys.exit(0)
else:
    app.config['AUTH_TOKEN'] = str(uuid4())
    with open(token_path, 'w') as f:
        f.write(app.config['AUTH_TOKEN'])

with open(os.path.join(os.getcwd(), sys.argv[1])) as f:
    file_data = f.read()

if os.path.isfile(custom_script_file_path):
    with open(custom_script_file_path) as f:
        custom_script_file_data = f.read()
else:
    custom_script_file_data = ''

cpus = get_cpu_data()
req_cpus = get_available_cpu_data()
mem = get_mem_data()
req_mem = get_available_mem_data()
node_data = list(zip(cpus, req_cpus, mem, req_mem))
node_data = sorted(node_data, key=lambda x: int(x[1][:-1]), reverse=True)
node_count = len(node_data)
replica_calculated = int(os.getenv("ORCA_NODES", node_count))
node_data = node_data[:replica_calculated]

base_cpu = min(list(zip(*node_data))[0])

if SAFE_SCHEDULING:
    nproc = min(map(lambda x: int(x[:-1]) // 1000, list(zip(*node_data))[1])) * replica_calculated
else:
    nproc = base_cpu * replica_calculated - SAFETY_CPU_SUBTRAHEND

file_data = file_data.replace("nprocs 0", f"nprocs {nproc}")

if f"nprocs {nproc}" in file_data:
    print(f"Running on {nproc} cpus.")

nproc_s = re.search(r"nprocs ([1-9][0-9]*)", file_data)

if nproc_s:
    maxcore = max(int(sum(map(lambda x: int(x[:-2]), list(zip(*node_data))[2 if not SAFE_SCHEDULING else 3])) / int(nproc_s.groups()[0])) - SAFETY_MEM_SUBTRAHEND, 500)
    file_data = file_data.replace("maxcore 0", f"maxcore {maxcore}")

    if f"maxcore {maxcore}" in file_data:
        print(f"Running with {maxcore} MB memory per cpu.")

cr = str(min(map(lambda x: int(x[:-1]), list(zip(*node_data))[1]))-500) + node_data[0][1][-1:]
m = str(min(map(lambda x: int(x[:-2]), list(zip(*node_data))[2]))+500) + node_data[0][2][-2:]
mr = str(min(map(lambda x: int(x[:-2]), list(zip(*node_data))[3]))-2000) + node_data[0][3][-2:]

if int(mr[:-2]) > int(m[:-2]):
    mr = m

if int(cr[:-1])/1000 > base_cpu+0.2:
    cr = base_cpu+0.2

template_values(app.config['AUTH_TOKEN'], POD_IP, file_data, base_cpu + 0.2, cr, m, mr, replica_calculated, ((" " + " ".join(sys.argv[2:])) if len(sys.argv) > 2 else ""), custom_script_file_data)

res = subprocess.run(f"helm template orca-executor {os.path.join(SCRIPT_PATH, 'charts', 'openmpi-cluster')} {f'--set extraFiles[0].path=/opt/enso/config --set-file extraFiles[0].file={enso_file_path}' if os.path.isfile(enso_file_path) else ''} -f {os.path.join(SCRIPT_PATH, 'values.yaml')} | kubectl apply -f -", capture_output=True, shell=True)
if res.returncode != 0:
    print("Failed to deploy orca-mpi cluster")
    print(res.stderr.decode("utf-8"))
    sys.exit(1)


if __name__ == '__main__':
    run_app()