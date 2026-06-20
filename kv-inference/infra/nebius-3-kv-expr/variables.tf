variable "project_id" {
  description = "Nebius project (parent) ID"
  type        = string
}

variable "subnet_id" {
  description = "Nebius VPC subnet ID in eu-north1"
  type        = string
}

variable "hf_token" {
  description = "HuggingFace API token for model download"
  type        = string
  sensitive   = true
}

variable "vllm_model" {
  description = "HuggingFace model ID to serve"
  type        = string
  default     = "Qwen/Qwen2.5-7B-Instruct"
}

variable "k8s_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.31"
}

variable "gpu_memory_utilization" {
  description = "Fraction of GPU memory reserved for KV cache (Run A=0.20, Run B=0.40)"
  type        = string
  default     = "0.20"
}