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
  }
}

provider "kubernetes" {
  host = "https://${nebius_mk8s_v1_cluster.kv_inference.status.control_plane.endpoints.public_endpoint}"

  cluster_ca_certificate = base64decode(
    nebius_mk8s_v1_cluster.kv_inference.status.control_plane.auth.cluster_ca_certificate
  )

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "nebius"
    args = [
      "mk8s", "v1", "cluster", "get-credentials",
      "--id", nebius_mk8s_v1_cluster.kv_inference.id,
      "--external",
      "--format", "json"
    ]
  }
}