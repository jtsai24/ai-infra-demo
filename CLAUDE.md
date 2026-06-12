# CLAUDE.md
Last updated: June 12, 2026

## Who I am

Jimmy — backend software engineer, 10+ years at Amazon building distributed microservices. Strong in Linux, Java/Python, AWS, distributed systems fundamentals. Actively transitioning into AI infrastructure engineering.

New to: Slurm, RDMA/InfiniBand, Ollama, vLLM, NCCL, Go operators, ArgoCD, GPU-specific tooling, Terraform (CDK background).

## How to work with me

Pair program with me — do not do the work for me.

- Explain what a command does before I run it
- Don't generate entire files unprompted — walk me through them section by section
- When I hit an error, help me understand what it means before giving the fix
- Call out footguns before they happen (leaked resources, wrong env vars, munge key permissions)
- Don't over-explain basic software engineering — I know distributed systems. Do explain GPU/RDMA/Slurm concepts clearly
- Ask me what I think before giving the answer on new concepts
- After writing to Notion, always give me a link to the page — I will always want to review it

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

Phase 4 — Local k3s Observability + Nebius Inference Stack

### Completed
- [x] Ollama local benchmarks
- [x] vLLM-metal installed and running locally (M4, MLX backend)
- [x] vLLM benchmark scripts (`measure_inference_vllm.py`, `load_test_vllm.py`)
- [x] Confirmed all three Go operator metrics present in vLLM `/metrics`
- [x] Decided vLLM over Ollama for inference stack (Prometheus metrics required by operator)

### In progress
- [ ] k3s up locally
- [ ] Prometheus + Grafana + Loki + Promtail running as pods, scraping vLLM-metal on host
- [ ] Load test Job wired into k3s, metrics visible in Grafana during run

### Up next
- [ ] Nebius Session 1 — single H100, vLLM pod, full observability, KV cache pressure data
- [ ] Local operator dev (after Nebius Session 1 data)
- [ ] Nebius Session 2 — Go operator demo + Loom recording

## Local k3s architecture decisions

- **Deployments**: Prometheus, Grafana, Loki, Promtail
- **Jobs**: single-request and load test scripts (run to completion)
- **Host (outside k3s)**: vLLM-metal at `host.docker.internal:8000` — cannot be containerized on Apple Silicon
- **No host-process observability**: purpose of local step is to de-risk Nebius; pods give near copy-paste manifests to Nebius
