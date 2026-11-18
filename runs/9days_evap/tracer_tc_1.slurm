#!/bin/bash
#SBATCH -J tracer_tc_1
#SBATCH -A ADCIRC
#SBATCH -o tracer_tc_1.o%j
#SBATCH -e tracer_tc_1.e%j
#SBATCH -p gg
#SBATCH -N 1
#SBATCH --tasks-per-node 64
#SBATCH -t 1:00:00
#SBATCH --mail-user=ashtonvcole@utexas.edu
#SBATCH --mail-type=all
source ../../scripts/tacc_env.sh
which python
date>tracer_tc_1.timing
time mpiexec -bind-to-core -n 64 python -u /work/09041/ashtonc/dev/github.com/ashtonvcole/TracerPost/main/src/tracer_post.py tracer_tc_1.toml
date>>tracer_tc_1.timing
