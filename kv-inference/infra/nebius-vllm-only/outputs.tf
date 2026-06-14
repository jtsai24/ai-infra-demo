output "cluster_id" {
  description = "Nebius MK8s cluster ID — use this for get-credentials"
  value       = nebius_mk8s_v1_cluster.kv_inference.id
}

output "cluster_public_endpoint" {
  description = "Kubernetes API public endpoint"
  value       = nebius_mk8s_v1_cluster.kv_inference.status.control_plane.endpoints.public_endpoint
}

output "get_credentials_cmd" {
  description = "Run this after terraform apply to configure kubectl"
  value       = "nebius mk8s v1 cluster get-credentials --id ${nebius_mk8s_v1_cluster.kv_inference.id} --external"
}

output "vllm_health_check_cmd" {
  description = "Validate vLLM is responding"
  value       = "kubectl exec -n default deploy/vllm -- curl -s http://localhost:8000/health"
}

output "vllm_test_inference_cmd" {
  description = "Send a test completion request to vLLM"
  value       = <<-EOT
    kubectl exec -n default deploy/vllm -- curl -s http://localhost:8000/v1/completions \
      -H 'Content-Type: application/json' \
      -d '{"model": "${var.vllm_model}", "prompt": "Hello", "max_tokens": 16}'
  EOT
}