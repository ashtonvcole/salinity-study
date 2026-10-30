#!/bin/bash
#SBATCH -J 9days_evap
#SBATCH -A ADCIRC
#SBATCH -o 9days_evap.o%j
#SBATCH -e 9days_evap.e%j
#SBATCH -p gh
#SBATCH -N 8
#SBATCH --tasks-per-node 1
#SBATCH -t 3:00:00
#SBATCH --mail-user=ashtonvcole@utexas.edu
#SBATCH --mail-type=all
date>run.timing
ibrun ./dgswem
date>>run.timing
