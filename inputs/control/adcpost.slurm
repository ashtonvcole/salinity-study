#!/bin/bash
#SBATCH -J adcpost
#SBATCH -A ADCIRC
#SBATCH -o adcpost.o%j
#SBATCH -e adcpost.e%j
#SBATCH -p gh-dev
#SBATCH -N 1
#SBATCH --tasks-per-node 1
#SBATCH -t 0:30:00
#SBATCH --mail-user=ashtonvcole@utexas.edu
#SBATCH --mail-type=all
date>adcpost.timing
./adcpost < post.txt
date>>adcpost.timing
