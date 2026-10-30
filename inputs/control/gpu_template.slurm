#!/bin/bash
#SBATCH -J 120m_wind_gpu
#SBATCH -A ADCIRC
#SBATCH -o 120m_wind_gpu.o%j
#SBATCH -e 120m_wind_gpu.e%j
#SBATCH -p gh
#SBATCH -N 8
#SBATCH --tasks-per-node 1
#SBATCH -t 3:00:00
#SBATCH --mail-user=ashtonvcole@utexas.edu
#SBATCH --mail-type=all
date>run.timing
ibrun ./dgswem
date>>run.timing
