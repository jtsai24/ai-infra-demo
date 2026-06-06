#!/bin/bash
#SBATCH --job-name=hello
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --partition=gpu
#SBATCH --output=/home/user/logs/%j_hello.out

srun hostname