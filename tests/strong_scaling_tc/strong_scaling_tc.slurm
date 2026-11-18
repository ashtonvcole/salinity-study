#!/bin/bash
#SBATCH -J strong_scaling_tc
#SBATCH -A ADCIRC
#SBATCH -o strong_scaling_tc.o%j
#SBATCH -e strong_scaling_tc.e%j
#SBATCH -p gg
#SBATCH -N 1
#SBATCH --tasks-per-node 144
#SBATCH -t 3:00:00
#SBATCH --mail-user=ashtonvcole@utexas.edu
#SBATCH --mail-type=all
source ../../scripts/tacc_env.sh
which python
date>strong_scaling_tc.timing
echo "nproc,wall_s,status" > strong_scaling_tc.csv
for NPROC in 1 2 4 8 16 32 64 128; do
    t0=$(date +%s.%n)
    mpiexec -n $NPROC python -u /work/09041/ashtonc/vista/dev/github.com/ashtonvcole/TracerPost/main/src/tracer_post.py strong_scaling_tc.toml
    stat=$?
    t1=$(date +%s.%n)
    echo "$NPROC,$(echo "$t1 - $t0" | bc -l),$stat" >> strong_scaling_tc.csv
done
date>>strong_scaling_tc.timing
