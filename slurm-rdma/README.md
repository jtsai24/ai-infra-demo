# Slurm + RDMA Cluster

A 2-node GPU cluster on [Nebius](https://nebius.com) with Slurm job scheduling and InfiniBand RDMA networking. Provisions from scratch with Terraform, configures with Ansible, and submits NCCL benchmarks as Slurm batch jobs.

## What this demonstrates

- Bare-metal GPU cluster provisioning with Terraform (Nebius provider)
- Multi-node Slurm cluster setup via Ansible: `slurmctld` controller + `slurmd` compute nodes
- Munge key synchronization, gres.conf, and slurm.conf configuration
- NCCL `all_reduce` benchmarks submitted as `sbatch` jobs across transport layers
- InfiniBand RDMA with GPU Direct (GDRDMA) — data moves GPU→IB→GPU without touching CPU

## Hardware

- **Nodes:** 2× Nebius `gpu-h100-sxm` (`8gpu-128vcpu-1600gb`)
- **GPUs:** 8× NVIDIA H100 80GB HBM3 per node (16 total)
- **Networking:** InfiniBand fabric-2 (`nebius_compute_v1_gpu_cluster`), mlx5_0–mlx5_7 active per node
- **MPI:** HPC-X OpenMPI 4.1.7 (pre-installed by Nebius at `/usr/mpi/gcc/openmpi-4.1.7a1`)

## Benchmark results

4-step NCCL job progression, each run as a Slurm `sbatch` job:

| Job | Config | Transport | Peak busbw |
|-----|--------|-----------|-----------|
| `nccl_1_single_gpu` | 1 node, 1 GPU, no MPI | on-GPU | — |
| `nccl_2_nvlink` | 1 node, 8 GPUs, no MPI | NVLink | **398 GB/s** |
| `nccl_3_mpi_tcp` | 2 nodes, 16 GPUs, MPI | TCP (eth0) | 2.84 GB/s |
| `nccl_4_ib` | 2 nodes, 16 GPUs, MPI | IB/GDRDMA | **388 GB/s** |

IB/GDRDMA is **136× faster than TCP** at 256M message size. Raw output files in `benchmarks/`.

## Repo layout

```
slurm-rdma/
  infra/          Terraform: 2-node H100 cluster with IB gpu_cluster resource
  ansible/        Playbooks: node config, Slurm install, munge sync, nccl-tests build
  jobs/           Slurm job scripts (sbatch) for each benchmark step
  benchmarks/     NCCL output files with busbw numbers
```

## Branches

- **`main`** — stable baseline: Terraform config, Ansible playbook, benchmark output files
- **`ib-benchmark`** — full IB benchmark session: 8-GPU Terraform config with `gpu_cluster` resource, 4-step job scripts, all raw logs. Use this branch to reproduce the benchmark results.

## Quickstart

> To reproduce the IB benchmarks, check out the `ib-benchmark` branch first:
> ```bash
> git checkout ib-benchmark
> ```

**1. Provision**
```bash
cd infra
cp terraform.tfvars.example terraform.tfvars  # fill in project_id, subnet_id
terraform init && terraform apply -auto-approve
```

**2. Update inventory**
```bash
# Edit ansible/inventory.ini with IPs from terraform output
```

**3. Configure cluster**
```bash
cd ansible
ansible-playbook -i inventory.ini playbook.yml
ansible-playbook -i inventory.ini nccl.yml      # builds nccl-tests on all nodes
```

**4. Run benchmarks**
```bash
ansible-playbook -i inventory.ini jobs_nccl_1_single_gpu.yml
ansible-playbook -i inventory.ini jobs_nccl_3_mpi_tcp.yml
ansible-playbook -i inventory.ini jobs_nccl_4_ib.yml
ansible-playbook -i inventory.ini jobs_nccl_2_nvlink.yml
```

**5. Destroy**
```bash
cd infra && terraform destroy -auto-approve
# Verify zero instances in Nebius console
```

## Key lessons learned

- Nebius InfiniBand requires `nebius_compute_v1_gpu_cluster` resource with `infiniband_fabric = "fabric-2"` — only supported on 8-GPU preset (`8gpu-128vcpu-1600gb`)
- Slurm 21.08.5 does not support bracket glob syntax in `gres.conf` — requires explicit per-GPU lines (`File=/dev/nvidia0` through `File=/dev/nvidia7`)
- `NCCL_IB_HCA=mlx5` selects all mlx5_* devices; `NCCL_IB_HCA=mlx5_0` only uses one
- MPI job scripts must use `-g 1` (GPUs per rank), not `-g 8`; direct binary invocations need `LD_LIBRARY_PATH` set explicitly