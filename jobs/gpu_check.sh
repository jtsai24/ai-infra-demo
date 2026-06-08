#!/bin/bash
#SBATCH --job-name=gpu_check
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=8
#SBATCH --gres=gpu:8
#SBATCH --partition=gpu
#SBATCH --output=/home/user/logs/%j_gpu_check.out

srun nvidia-smi -L
