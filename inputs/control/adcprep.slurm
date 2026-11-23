#!/bin/bash
#SBATCH -J adcprep
#SBATCH -A ADCIRC
#SBATCH -o adcprep.o%j
#SBATCH -e adcprep.e%j
#SBATCH -p gh-dev
#SBATCH -N 1
#SBATCH --tasks-per-node 1
#SBATCH -t 1:00:00
#SBATCH --mail-user=ashtonvcole@utexas.edu
#SBATCH --mail-type=all
date>adcprep.timing
./adcprep < prep.txt
date>>adcprep.timing
