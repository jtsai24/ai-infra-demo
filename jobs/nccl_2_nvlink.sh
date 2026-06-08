#!/bin/bash
#SBATCH --job-name=nccl-nvlink
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:8
#SBATCH --partition=gpu
#SBATCH --output=/home/user/logs/%j_nccl_nvlink.out

# Single node, 8 GPUs, no MPI
# Goal: confirm NCCL can use NVLink across all 8 GPUs on one node
/home/user/nccl-tests/build/all_reduce_perf -b 8 -e 128M -f 2 -g 8