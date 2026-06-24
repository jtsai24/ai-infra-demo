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

**Nebius Session 1 — vLLM on H100 (single node):**
- Provisioned Nebius managed k8s cluster with 1× H100 SXM node via Terraform
- Deployed vLLM serving `Qwen/Qwen2.5-0.5B-Instruct` as a Kubernetes pod
- Validated OpenAI-compatible inference API end-to-end via `kubectl exec`
- Confirmed all three operator metrics live on `/metrics`: `vllm:kv_cache_usage_perc`, `vllm:num_requests_running`, `vllm:num_requests_waiting`
- Cluster torn down cleanly with `terraform destroy`

**Nebius Session 2 — vLLM + Observability Stack on H100:**
- Deployed Prometheus, Loki, Promtail, Grafana via Helm into the same cluster as vLLM
- Prometheus confirmed scraping vLLM `/metrics` (Targets page showed UP)
- Loki log pipeline confirmed end-to-end: Promtail → Loki → 720 lines ingested → Grafana queryable
- Grafana dashboard showing both metrics and log panels live
- H100 single-request: TTFT **366ms** warm, TPOT **1.8ms/token**, **278 tok/s** (full-precision vs M4's 4-bit)
- All services on NodePort — no port-forwarding needed during the session

**Nebius Session 3 — KV Cache Experiments (H100, Qwen2.5-7B-Instruct):**

Four controlled experiments measuring how vLLM configuration levers affect KV cache, latency, and throughput under concurrent multi-turn load. All runs on a single Nebius H100 80GB SXM with full Prometheus/Grafana observability.

| Experiment | Variable | Key Finding | Issue |
|---|---|---|---|
| [Exp 1 — KV Cache Size vs Throughput](https://github.com/jtsai24/ai-infra-demo/issues/5) | `gpu_memory_utilization` 0.30 vs 0.70 | At 0.30, KV cache hit 100% and requests queued (TTFT p95 ~6s); at 0.70, queue stayed at 0 and TTFT p95 ~3.5s | #5 |
| [Exp 2 — Prefix Caching](https://github.com/jtsai24/ai-infra-demo/issues/7) | Prefix cache OFF vs ON | Enabling prefix cache cut TTFT p95 **10×** (4–5s → 0.4–0.5s) and halved KV cache consumption — zero-cost optimization | #7 |
| [Exp 3 — Weight Quantization](https://github.com/jtsai24/ai-infra-demo/issues/8) | bf16 vs INT4 GPTQ | INT4 weights 2.6× smaller (14GB → 5.3GB), TPOT improved 27%, 38% more requests completed; quality degradation negligible | #8 |
| [Exp 4 — Chunked Prefill](https://github.com/jtsai24/ai-infra-demo/issues/9) | Chunked prefill OFF vs ON | Without chunking, a 2000-token inject caused 10–15× TPOT spikes (6ms → 50–93ms) in concurrent sessions; chunking eliminated all spikes | #9 |

**Local observability stack validated (k3s + OrbStack on Apple Silicon):**
- Prometheus scraping vLLM metrics — `vllm:kv_cache_usage_perc`, `vllm:num_requests_running`, `vllm:num_requests_waiting`
- Loki + Promtail collecting vLLM logs
- Grafana dashboard with KV cache, request pipeline, latency, and log panels
- Load test script with one-shot and continuous modes

## Stack

Terraform · Ansible · Slurm · NCCL · InfiniBand · RDMA · Nebius · H100 SXM · HPC-X MPI · vLLM · Prometheus · Grafana · Loki · Helm · k3s

## Tradeoffs & Known Limitations

**Why Terraform over Pulumi:** Terraform's declarative model does not natively support imperative ordering of side effects. The Nebius managed Kubernetes provider writes cluster credentials to `~/.kube/config` via a CLI command (`nebius mk8s v1 cluster get-credentials`) rather than emitting ExecCredential JSON to stdout, which means the kubeconfig population cannot be expressed as a Terraform resource. This forces a manual step between Stage 1 (cluster + node group) and Stage 2 (Kubernetes + Helm resources), breaking the single-apply declarative model. Nebius provides an official Pulumi provider that would solve this cleanly — since Pulumi uses real Go/Python code, the credential fetch can be expressed as a regular function call with explicit ordering, enabling a single `pulumi up` with no manual intervention. Terraform was chosen here for portfolio visibility given its dominance in AI infra shops, but this is the concrete cost of that choice.