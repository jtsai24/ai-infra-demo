#!/bin/bash
#SBATCH --job-name=nccl-allreduce
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --partition=gpu
#SBATCH --output=/home/user/logs/%j_nccl.out

export NCCL_SOCKET_IFNAME=eth0
export NCCL_DEBUG=WARN  # reduce noise; use INFO if debugging

mpirun --np 2 \
  --host node1,node2 \
  --mca btl_tcp_if_include eth0 \
  /home/user/nccl-tests/build/all_reduce_perf -b 8 -e 256M -f 2 -g 1