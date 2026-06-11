# AI Infrastructure Portfolio

A portfolio project demonstrating AI infrastructure engineering skills targeting L1-L3 roles at CoreWeave, Anthropic, and Nvidia.

## Projects

### [slurm-rdma/](slurm-rdma/) — Slurm + RDMA Cluster ✅
2-node H100 GPU cluster on Nebius with Slurm job scheduling and InfiniBand RDMA. Provisions with Terraform, configures with Ansible, and runs NCCL `all_reduce` benchmarks as batch jobs.

**Key results:**
- IB/GDRDMA: **388 GB/s** bus bandwidth (2 nodes, 16 GPUs)
- NVLink: **398 GB/s** bus bandwidth (1 node, 8 GPUs)
- TCP baseline: 2.84 GB/s — IB is **136× faster**
- Transport confirmed as `NET/IB/GDRDMA` via NCCL debug logs

### [kv-inference/](kv-inference/) — KV-Aware Inference Platform 🚧
vLLM inference gateway with a custom Go Kubernetes operator. In progress.

## Stack

Terraform · Ansible · Slurm · NCCL · InfiniBand · RDMA · Nebius · H100 SXM · HPC-X MPI