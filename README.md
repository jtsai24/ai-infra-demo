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

**Local observability stack validated (k3s + OrbStack on Apple Silicon):**
- Prometheus scraping vLLM metrics — `vllm:kv_cache_usage_perc`, `vllm:num_requests_running`, `vllm:num_requests_waiting`
- Loki + Promtail collecting vLLM logs
- Grafana dashboard with KV cache, request pipeline, latency, and log panels
- Load test script with one-shot and continuous modes

**To run locally (Apple Silicon, vLLM-metal):**
```bash
# Start vLLM
source ~/.venv-vllm-metal/bin/activate && vllm serve mlx-community/Qwen2.5-0.5B-Instruct-4bit 2>&1 | tee ~/vllm.log

# Deploy observability stack
helm install prometheus prometheus-community/prometheus -f kv-inference/k8s/helm/prometheus-values.yaml
helm install loki grafana/loki -f kv-inference/k8s/helm/loki-values.yaml
helm install promtail grafana/promtail -f kv-inference/k8s/helm/promtail-values.yaml
helm install grafana grafana/grafana -f kv-inference/k8s/helm/grafana-values.yaml

# Access Grafana
kubectl port-forward svc/grafana 3000:80
```

## Stack

Terraform · Ansible · Slurm · NCCL · InfiniBand · RDMA · Nebius · H100 SXM · HPC-X MPI · vLLM · Prometheus · Grafana · Loki · Helm · k3s