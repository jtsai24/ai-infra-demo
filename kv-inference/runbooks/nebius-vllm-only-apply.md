# Runbook: Nebius Session 1 — vLLM on H100

Directory: `kv-inference/infra/nebius-vllm-only/`

## Why two steps?

The Terraform `kubernetes` provider must authenticate to the cluster at plan/apply time.
On Nebius, `nebius mk8s v1 cluster get-credentials` writes credentials to `~/.kube/config`
— it does **not** emit ExecCredential JSON to stdout, so the `exec {}` block pattern
does not work. The cluster must exist and kubeconfig must be populated before Terraform
can create any Kubernetes resources.

---

## Step 1 — Provision cluster and node group

```bash
cd /Users/jimmy/ai-infra-demo/kv-inference/infra/nebius-vllm-only

terraform apply \
  -target=nebius_mk8s_v1_cluster.kv_inference \
  -target=nebius_mk8s_v1_node_group.h100
```

Takes ~5 minutes. When it completes, verify the cluster is RUNNING (not just created):

```bash
terraform output cluster_id   # copy this value

nebius mk8s v1 cluster get --id <cluster_id>
# Look for: "status": "RUNNING"
```

Do not proceed until status is RUNNING.

---

## Step 2 — Populate kubeconfig

```bash
nebius mk8s v1 cluster get-credentials --id <cluster_id> --external
```

Verify the context name matches what's in `main.tf` (`config_context = "nebius-kv-inference"`):

```bash
kubectl config get-contexts
# Expected: a context named "nebius-kv-inference"
```

If the name differs, update `config_context` in `main.tf` before Step 3.

Verify kubectl can reach the cluster:

```bash
kubectl get nodes
# Expected: one node, status Ready
```

---

## Step 3 — Apply Kubernetes resources

```bash
terraform apply
```

This creates: HF token Secret, vLLM Deployment, ClusterIP Service.

---

## Step 4 — Wait for vLLM to be ready

vLLM needs to download the model and load weights — takes a few minutes.

```bash
# Watch pod status — wait for 1/1 Running
kubectl get pods -n default -w
```

The startup probe allows up to 10 minutes (`failure_threshold=60`, `period_seconds=10`).
If the pod is stuck in `Init` or `Pending`, check:

```bash
kubectl describe pod -n default -l app=vllm
kubectl logs -n default deploy/vllm
```

---

## Step 5 — Validate vLLM is working

```bash
# Health check — should return: {}
kubectl exec -n default deploy/vllm -- curl -s http://localhost:8000/health

# Test inference
kubectl exec -n default deploy/vllm -- curl -s http://localhost:8000/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "Qwen/Qwen2.5-0.5B-Instruct", "prompt": "Hello", "max_tokens": 16}'
```

Expected: JSON response with a `choices` array containing generated text.

```bash
# Check metrics endpoint is live (needed for observability)
kubectl exec -n default deploy/vllm -- curl -s http://localhost:8000/metrics | head -20
# Look for lines starting with: vllm:kv_cache_usage_perc, vllm:num_requests_running
```

---

## Teardown

**Always destroy when done — this is a paid session.**

```bash
terraform destroy
```

Then verify in the Nebius console that zero instances remain — not just "stopped".

Also remove the kubeconfig context to avoid stale config:

```bash
kubectl config delete-context nebius-kv-inference
```