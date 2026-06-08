#!/bin/bash
#SBATCH --job-name=nccl-mpi-tcp
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=8
#SBATCH --gres=gpu:8
#SBATCH --partition=gpu
#SBATCH --output=/home/user/logs/%j_nccl_mpi_tcp.out

# Two nodes, 8 GPUs each, MPI, TCP transport
# Goal: confirm MPI + multi-node NCCL works before enabling IB
export NCCL_IB_DISABLE=1
export NCCL_SOCKET_IFNAME=eth0
export NCCL_DEBUG=INFO  # INFO required to confirm Transport: TCP in logs

/usr/mpi/gcc/openmpi-4.1.7a1/bin/mpirun --np 16 \
  --host node1:8,node2:8 \
  /home/user/nccl-tests/build/all_reduce_perf -b 8 -e 128M -f 2 -g 8