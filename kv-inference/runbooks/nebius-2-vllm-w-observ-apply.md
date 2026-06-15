# Runbook: Nebius Session 2 — vLLM + Observability Stack on H100

Directory: `kv-inference/infra/nebius-2-vllm-w-observ/`

## Why four steps?

Same kubeconfig chicken-and-egg problem as Session 1 (see Session 1 runbook).
Additionally, the observability stack (Step 4) must not be deployed until vLLM
is confirmed `1/1 Running` and `/metrics` is live — otherwise Prometheus starts
scraping a dead target and Promtail has no pod logs to collect.

---

## Step 1 — Provision cluster and node group

```bash
cd /Users/jimmy/ai-infra-demo/kv-inference/infra/nebius-2-vllm-w-observ

terraform apply -target=nebius_mk8s_v1_cluster.kv_inference -target=nebius_mk8s_v1_node_group.h100
```

Takes ~5 minutes. Verify RUNNING before proceeding:

```bash
terraform output cluster_id   # copy this value

nebius mk8s v1 cluster get --id <cluster_id>
# Look for: "status": "RUNNING"
```

---

## Step 2 — Populate kubeconfig

```bash
nebius mk8s v1 cluster get-credentials --id <cluster_id> --external
```

Verify context name and cluster reachability:

```bash
kubectl config get-contexts   # note the context name
kubectl get nodes             # Expected: one node, status Ready
```

If the context name differs from what's computed in `main.tf`, update `config_context` in `main.tf` before Step 3.

---

## Step 3 — Deploy vLLM

```bash
terraform apply -target=kubernetes_secret.hf_token -target=kubernetes_deployment.vllm -target=kubernetes_service.vllm
```

Wait for vLLM to be ready (model download + weight load, ~5 min):

```bash
kubectl get pods -n default -w
# Wait for: vllm-xxx   1/1   Running
```

Validate vLLM before proceeding to Step 4:

```bash
# Health check — should return: {}
kubectl exec -n default deploy/vllm -- curl -s http://localhost:8000/health

# Metrics endpoint — must be live before Prometheus is deployed
kubectl exec -n default deploy/vllm -- curl -s http://localhost:8000/metrics | grep -E "kv_cache|num_requests"
```

Do not proceed to Step 4 until metrics are confirmed live.

---

## Step 4 — Deploy observability stack

```bash
terraform apply
```

This deploys: Prometheus, Loki, Promtail, Grafana as Helm releases.

Wait for all pods to be running:

```bash
kubectl get pods -n default -w
# Expected: all pods 1/1 Running — prometheus, loki, promtail, grafana
```

---

## Step 5 — Validate observability stack

**Prometheus scraping vLLM:**

```bash
kubectl port-forward svc/prometheus-server 9090:80
```

Open `http://localhost:9090/targets` — vLLM job should show `UP`.

**Grafana:**

```bash
# Get admin password
kubectl get secret -n default grafana -o jsonpath='{.data.admin-password}' | base64 --decode

# Forward to localhost
kubectl port-forward svc/grafana 3000:80
```

Open `http://localhost:3000`, log in as `admin`. Import dashboard from:
`kv-inference/observability/grafana/dashboards/vllm-dashboard.json`

---

## Step 6 — Run load test

Port-forward vLLM so local scripts can reach it:

```bash
kubectl port-forward -n default svc/vllm 8000:8000
```

In a separate terminal, run the load test:

```bash
cd /Users/jimmy/ai-infra-demo
python kv-inference/scripts/load_test_vllm.py --continuous
```

Watch KV cache pressure and request pipeline metrics build up in Grafana.

---

## Teardown

**Always destroy when done — this is a paid session.**

```bash
terraform destroy
```

Verify zero instances in the Nebius console — not just "stopped".

Remove the kubeconfig context:

```bash
terraform output delete_context_cmd
# Run the printed command
```