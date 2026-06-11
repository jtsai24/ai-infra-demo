# Slurm + RDMA Cluster — IB Benchmark Branch

This branch contains the full InfiniBand benchmark session: 8-GPU Terraform config, 4-step NCCL job progression, Ansible playbooks, and raw benchmark output.

> **Note:** This branch is kept as a permanent historical reference. Do not merge or delete it.
> The `main` branch contains the restructured repo with benchmark results copied over.

## What's here

```
infra/        Terraform: 2-node H100 cluster with nebius_compute_v1_gpu_cluster (fabric-2)
ansible/      Playbooks: node config, Slurm, munge sync, nccl-tests build, 4 job playbooks
jobs/         Slurm job scripts for each benchmark step
benchmarks/   NCCL output files (summarized + raw logs)
```

## Hardware

- **Nodes:** 2× Nebius `gpu-h100-sxm` (`8gpu-128vcpu-1600gb`)
- **GPUs:** 8× NVIDIA H100 80GB HBM3 per node (16 total)
- **Networking:** InfiniBand fabric-2, mlx5_0–mlx5_7 active per node
- **MPI:** HPC-X OpenMPI 4.1.7 at `/usr/mpi/gcc/openmpi-4.1.7a1`

## Benchmark results

| Job | Config | Transport | Peak busbw |
|-----|--------|-----------|-----------|
| `nccl_1_single_gpu` | 1 node, 1 GPU, no MPI | on-GPU | — |
| `nccl_2_nvlink` | 1 node, 8 GPUs, no MPI | NVLink | **398 GB/s** |
| `nccl_3_mpi_tcp` | 2 nodes, 16 GPUs, MPI | TCP (eth0) | 2.84 GB/s |
| `nccl_4_ib` | 2 nodes, 16 GPUs, MPI | IB/GDRDMA | **388 GB/s** |

IB/GDRDMA is **136× faster than TCP** at 256M. Transport confirmed as `NET/IB/GDRDMA` in NCCL debug logs.

## Reproducing the benchmarks

**1. Provision**
```bash
cd infra
cp terraform.tfvars.example terraform.tfvars  # fill in project_id, subnet_id
terraform init && terraform apply -auto-approve
```

**2. Update inventory**
```bash
# Edit ansible/inventory.ini with IPs from terraform output
ssh-keygen -R <node1_ip> && ssh-keygen -R <node2_ip>
```

**3. Configure cluster**
```bash
cd ansible
ansible-playbook -i inventory.ini playbook.yml
ansible-playbook -i inventory.ini nccl.yml
```

**4. Run benchmarks in order**
```bash
ansible-playbook -i inventory.ini jobs_nccl_1_single_gpu.yml
ansible-playbook -i inventory.ini jobs_nccl_3_mpi_tcp.yml
ansible-playbook -i inventory.ini jobs_nccl_4_ib.yml
ansible-playbook -i inventory.ini jobs_nccl_2_nvlink.yml   # NVLink last
```

**5. Destroy**
```bash
cd infra && terraform destroy -auto-approve
# Verify zero instances in Nebius console
```

## Key gotchas

- `libmpi.so.40` not found when calling binary directly — add `LD_LIBRARY_PATH=/usr/mpi/gcc/openmpi-4.1.7a1/lib` for jobs without `mpirun`
- MPI jobs require `-g 1` (GPUs per rank), not `-g 8`
- Slurm 21.08.5 requires explicit per-GPU lines in `gres.conf` — no bracket glob syntax
- `NCCL_IB_HCA=mlx5` uses all mlx5_* devices; `mlx5_0` only uses one