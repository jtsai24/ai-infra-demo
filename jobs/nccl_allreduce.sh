#!/bin/bash
#SBATCH --job-name=nccl-allreduce
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=8
#SBATCH --gres=gpu:8
#SBATCH --partition=gpu
#SBATCH --output=/home/user/logs/%j_nccl.out

export NCCL_IB_DISABLE=0
export NCCL_IB_HCA=mlx5_0  # placeholder — verify with ibv_devices after nodes come up
export NCCL_DEBUG=INFO  # INFO required to confirm Transport: IBV in logs

/usr/mpi/gcc/openmpi-4.1.7a1/bin/mpirun --np 16 \
  --host node1:8,node2:8 \
  /home/user/nccl-tests/build/all_reduce_perf -b 8 -e 256M -f 2 -g 8