#!/bin/bash
#SBATCH --job-name=nccl-single-gpu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --partition=gpu
#SBATCH --output=/home/user/logs/%j_nccl_single_gpu.out

# Simplest possible NCCL test: 1 node, 1 GPU, no MPI
# Goal: confirm nccl-tests binary runs and NCCL initializes
/home/user/nccl-tests/build/all_reduce_perf -b 8 -e 128M -f 2 -g 1