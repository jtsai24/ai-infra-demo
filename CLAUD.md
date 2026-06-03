# CLAUDE.md
Last updated: June 1, 2026

## Who I am

Jimmy — backend software engineer, 10+ years at Amazon building distributed microservices. Strong in Linux, Java/Python, AWS, distributed systems fundamentals. Actively transitioning into AI infrastructure engineering.

New to: Slurm, RDMA/InfiniBand, NCCL, Go operators, vLLM, ArgoCD, GPU-specific tooling, Terraform (CDK background).

## How to work with me

Pair program with me — do not do the work for me.

- Explain what a command does before I run it
- Don't generate entire files unprompted — walk me through them section by section
- When I hit an error, help me understand what it means before giving the fix
- Call out footguns before they happen (leaked resources, wrong env vars, munge key permissions)
- Don't over-explain basic software engineering — I know distributed systems. Do explain GPU/RDMA/Slurm concepts clearly
- Ask me what I think before giving the answer on new concepts

## Project goal

Build a portfolio demo for AI infra roles (CoreWeave, Anthropic, Nvidia L1-L3):

- 2-node GPU cluster on Nebius with Slurm
- RDMA/NCCL benchmarks submitted as batch jobs
- vLLM inference gateway managed by a custom Go Kubernetes operator
- Prometheus/Grafana observability
- GitOps via ArgoCD
- Packaged as a GitHub repo with a 5-minute Loom demo

## Nebius environment

- Region: eu-north1
- IDs (project, subnet, image) are in `infra/terraform.tfvars` (gitignored)

## Vendor decisions

- Primary cloud: Nebius (real IB fabric, first-party Terraform provider, Andy Bo Wu uses it in prod)
- Fallback: Lambda Labs (has IB, ~same price, weaker Terraform provider)
- Rejected: vast.ai, RunPod, TensorDock — no RDMA between nodes

## Budget discipline

- Total GPU budget: under $500
- Phase 3 real hardware target: under 4 billable hours (~$25-30)
- Always run terraform destroy when done
- Always verify zero instances in Nebius console after destroy — not just "stopped"
- All RDMA debugging done locally with Soft-RoCE (free) before the paid session

## Current phase

Phase 1, Week 1 — Foundation

- [x] Nebius account created
- [x] Project ID and Subnet ID found
- [x] Claude Code installed and authenticated on Pro
- [ ] Terraform installed
- [ ] Nebius CLI installed and authenticated
- [ ] CPU VM validation loop (provision → SSH → destroy)
- [ ] GPU cluster provisioned (main Phase 1 goal)
- [ ] Ansible playbook runs clean
- [ ] ib_write_bw succeeds across both nodes
