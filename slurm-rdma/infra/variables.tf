variable "project_id" {
  description = "Nebius project ID (parent_id for resources)"
  type        = string
  sensitive   = true
}

variable "subnet_id" {
  description = "VPC subnet ID for the network interface"
  type        = string
  sensitive   = true
}
