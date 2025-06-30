# Chemistry distributed pack

## Description

Docker image with browser-accessible UI based on [selkies](https://github.com/selkies-project/docker-selkies-egl-desktop/blob/main/selkies-gstreamer-entrypoint.sh) project for launching distributed calculations on kubernetes cluster with orca, crest, xtb and enso.

## Usage

```bash
orca-executor --help

Takes .inp file and any set of args to pass to orca function.

If .inp file contains entry 'nprocs 0' it will be replaced
          with number of available processes automatically.

If .inp file contains entry 'maxcore 0' it will be replaced
              with calculated memory per core automatically.

Use 'orca-executor show nproc' to see available cpus in cluster.

Use 'orca-executor show logs' to see orca logs.

Use environment variable ORCA_NODES to overwrite number of worker nodes,
                                       useful for one node computations.

Use environment variable SAFE_SCHEDULING to enforce using maximum guaranteed cpus and memory instead of maximum potentially available, useful to avoid crashes due to resource over-scheduling, possible values: true/false, default: false.

Use environment variable ORCA_SHARED_MEMORY_ENABLED to mount external volume for shared memory,
                    useful if you run out of memory, possible values: true/false, default: true.

Use environment variable ORCA_SHARED_MEMORY_SIZE to set shared memory size if enabled,
                         possible values: XGi/XMi/XKi, where X - integer, default: 2Gi.

Use 'orca-executor exit' to finish orca gracefully.


To run custom calculations, e.g. enso, place your bash code in run.sh file.

ORCA fullpath can be obtained with the command "`echo $PATH | awk 'BEGIN{FS=":"; OFS="\n"} {$1=$1} 1' | grep orca | head -n 1`/orca".


For running enso calculations place .ensorc file in the same directory with following config:

#NMR data
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
omp: 0                                     # number e.g. 4
```
