# Runbook: nebius-vllm-only terraform apply

Directory: `kv-inference/infra/nebius-vllm-only/`

## Why two steps?

The Terraform `kubernetes` provider must authenticate to the cluster at plan/apply time.
On Nebius, `nebius mk8s v1 cluster get-credentials` writes credentials to `~/.kube/config`
— it does **not** emit ExecCredential JSON to stdout, so the `exec {}` block pattern
does not work. The cluster must exist and kubeconfig must be populated before Terraform
can create any Kubernetes resources.

## Step 1 — Provision cluster and node group

```bash
cd kv-inference/infra/nebius-vllm-only

terraform init
terraform apply \
  -target=nebius_mk8s_v1_cluster.kv_inference \
  -target=nebius_mk8s_v1_node_group.h100
```

Wait for the cluster to reach RUNNING state (~5 min). Get the cluster ID from the output:

```bash
terraform output cluster_id
```

## Step 2 — Populate kubeconfig

```bash
nebius mk8s v1 cluster get-credentials \
  --id <cluster_id> --external
```

Verify the context name written by the CLI — it must match `config_context` in `main.tf`:

```bash
kubectl config get-contexts
```

The expected context name is `nebius-kv-inference`. If it differs, update `config_context`
in `main.tf` before proceeding.

## Step 3 — Apply Kubernetes resources

```bash
terraform apply
```

This creates the HF token Secret, vLLM Deployment, and ClusterIP Service.

## Validation

```bash
# Check pod is running
kubectl get pods -n default

# Health check
kubectl exec -n default deploy/vllm -- curl -s http://localhost:8000/health

# Test inference
kubectl exec -n default deploy/vllm -- curl -s http://localhost:8000/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "Hello", "max_tokens": 16}'
```

## Teardown

```bash
terraform destroy
```

Verify zero instances in the Nebius console after destroy — not just "stopped".