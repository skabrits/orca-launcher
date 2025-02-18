from flask import Flask, request, Response
from uuid import uuid4
import subprocess
import zipfile
import jinja2
import signal
import socket
import sys
import os


PID = os.getpid()
try:
    SCRIPT_PATH = sys._MEIPASS
except AttributeError:
    SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
POD_IP = socket.gethostbyname(socket.gethostname())
OK = False


def get_cpu_data():
    res = subprocess.run(
        "kubectl top -l openmpi-capable=true nodes  | tail -n +2 | tr -d 'm%' | awk '{print int($2 * (100 / $3 - 1) / 1000) - 2}'",
        capture_output=True, shell=True)
    cpus = [int(x) for x in res.stdout.decode("utf-8").split("\n") if x != ""]
    return cpus


def cleanup():
    res = subprocess.run(
        f"helm template orca-executor {os.path.join(SCRIPT_PATH, 'charts', 'openmpi-cluster')} -f {os.path.join(SCRIPT_PATH, 'values.yaml')} | kubectl delete -f -",
        capture_output=True, shell=True)
    if res.returncode != 0:
        print(res.stderr.decode("utf-8"))
        return Response("Error cleaning up", status=400)


if len(sys.argv) < 2:
    print("Required .inp file to run!")
    print("Use --help or -h flag to see help.")
    sys.exit(1)

if "--help" in sys.argv or "-h" in sys.argv:
    print("Takes .inp file and any set of args to pass to orca function.")
    print("If .inp file contains entry 'nprocs 0' it will be replaced")
    print("         with number of available processes automatically.")
    print("Use 'orca-executor show nproc' to see available cpus in cluster.")
    print("Use environment variable ORCA_NODES to overwrite number of worker nodes")
    print("                                       useful for one node computations.")
    sys.exit(0)

if sys.argv[1] == "show":
    if sys.argv[2] == "nproc":
        cpus = get_cpu_data()
        print(min(cpus) * len(cpus) - 1)
        sys.exit(0)
    else:
        print("Use 'orca-executor show nproc' to see available cpus in cluster")
        sys.exit(0)

app = Flask(__name__)
app.config['UPLOAD_FILE'] = os.path.join(os.getcwd(), "results.zip")
app.config['AUTH_TOKEN'] = str(uuid4())

with open(os.path.join(os.getcwd(), sys.argv[1])) as f:
    file_data = f.read()

cpus = get_cpu_data()
nproc = min(cpus) * len(cpus) - 1

file_data = file_data.replace("nprocs 0", f"nprocs {nproc}")

if f"nprocs {nproc}" in file_data:
    print(f"Running on {nproc} cpus.")

jinja2_template = jinja2.Environment(loader=jinja2.FileSystemLoader(SCRIPT_PATH)).get_template("values.tpl.yaml")
values_data = jinja2_template.render(token=app.config['AUTH_TOKEN'], pod_ip=POD_IP, file=file_data, cpu_num=min(cpus)+0.2, replica_num=os.getenv("ORCA_NODES", len(cpus)), additional_params=((" " + " ".join(sys.argv[2:])) if len(sys.argv) > 2 else ""))

with open(os.path.join(SCRIPT_PATH, "values.yaml"), "w") as f:
    f.write(values_data)

res = subprocess.run(f"helm template orca-executor {os.path.join(SCRIPT_PATH, 'charts', 'openmpi-cluster')} -f {os.path.join(SCRIPT_PATH, 'values.yaml')} | kubectl apply -f -", capture_output=True, shell=True)
if res.returncode != 0:
    print("Failed to deploy orca-mpi cluster")
    print(res.stderr.decode("utf-8"))
    sys.exit(1)


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888)
    if not OK:
        print("Error occurred!")
        cleanup()