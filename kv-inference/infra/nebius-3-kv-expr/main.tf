# Two-step apply required — kubernetes provider cannot auth until the cluster
# exists and ~/.kube/config is populated. Apply in this order:
#
#   Step 1: provision cluster + node group only
#     terraform apply -target=nebius_mk8s_v1_cluster.kv_inference \
#                     -target=nebius_mk8s_v1_node_group.h100
#
#   Step 2: populate kubeconfig (nebius CLI writes to ~/.kube/config,
#           it does NOT emit ExecCredential JSON to stdout)
#     nebius mk8s v1 cluster get-credentials \
#       --id <cluster_id> --external
#     # Verify context name: kubectl config get-contexts
#     # config_context in this file must match — default is "nebius-kv-inference"
#
#   Step 3: apply vLLM (k8s Secret + Deployment + Service)
#     terraform apply -target=kubernetes_secret.hf_token \
#                     -target=kubernetes_deployment.vllm \
#                     -target=kubernetes_service.vllm
#
#   Step 4: verify vLLM is 1/1 Running and /metrics is live, then:
#     terraform apply

terraform {
  required_providers {
    nebius = {
      source  = "nebius/nebius"
      version = "~> 0.2"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
  }
}

provider "nebius" {
  profile = {
    name = "default"
  }
}

resource "nebius_mk8s_v1_cluster" "kv_inference" {
  name      = "kv-inference"
  parent_id = var.project_id

  control_plane = {
    subnet_id = var.subnet_id
    version   = var.k8s_version

    endpoints = {
      public_endpoint = {}
    }

    etcd_cluster_size = 1
  }
}

resource "nebius_mk8s_v1_node_group" "h100" {
  name      = "h100-workers"
  parent_id = nebius_mk8s_v1_cluster.kv_inference.id

  fixed_node_count = 1

  template = {
    resources = {
      platform = "gpu-h100-sxm"
      preset   = "1gpu-16vcpu-200gb"
    }

    boot_disk = {
      type           = "NETWORK_SSD"
      size_gibibytes = 200
    }

    gpu_settings = {
      drivers_preset = "cuda12"
    }

    os = "ubuntu22.04"

    network_interfaces = [
      {
        subnet_id         = var.subnet_id
        public_ip_address = {}
      }
    ]

    cloud_init_user_data = <<-EOT
      #cloud-config
      users:
        - name: user
          sudo: ALL=(ALL) NOPASSWD:ALL
          shell: /bin/bash
          ssh_authorized_keys:
            - ${file("../../credentials/public_openssh.pub")}
    EOT
  }
}

provider "kubernetes" {
  host = nebius_mk8s_v1_cluster.kv_inference.status.control_plane.endpoints.public_endpoint

  cluster_ca_certificate = nebius_mk8s_v1_cluster.kv_inference.status.control_plane.auth.cluster_ca_certificate

  config_path    = "~/.kube/config"
  # Context name written by: nebius mk8s v1 cluster get-credentials --external
  # Pattern observed: nebius-mk8s-<cluster-name>-<cluster-id>
  config_context = "nebius-mk8s-${nebius_mk8s_v1_cluster.kv_inference.name}-${replace(nebius_mk8s_v1_cluster.kv_inference.id, "mk8scluster-", "")}"
}

provider "helm" {
  kubernetes {
    host                   = nebius_mk8s_v1_cluster.kv_inference.status.control_plane.endpoints.public_endpoint
    cluster_ca_certificate = nebius_mk8s_v1_cluster.kv_inference.status.control_plane.auth.cluster_ca_certificate
    config_path            = "~/.kube/config"
    config_context         = "nebius-mk8s-${nebius_mk8s_v1_cluster.kv_inference.name}-${replace(nebius_mk8s_v1_cluster.kv_inference.id, "mk8scluster-", "")}"
  }
}