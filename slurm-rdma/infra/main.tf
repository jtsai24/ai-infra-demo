terraform {
  required_providers {
    nebius = {
      source  = "nebius/nebius"
      version = "~> 0.2"
    }
  }
}

provider "nebius" {
  profile = {
    name = "default"
  }
}

resource "nebius_compute_v1_disk" "node1_disk" {
  name           = "h100-node1-disk"
  parent_id      = var.project_id
  type           = "NETWORK_SSD"
  size_gibibytes = 200
  source_image_family = {
    image_family = "ubuntu22.04-cuda12"
  }
}

resource "nebius_compute_v1_disk" "node2_disk" {
  name           = "h100-node2-disk"
  parent_id      = var.project_id
  type           = "NETWORK_SSD"
  size_gibibytes = 200
  source_image_family = {
    image_family = "ubuntu22.04-cuda12"
  }
}

resource "nebius_compute_v1_instance" "node1" {
  name      = "h100-node1"
  parent_id = var.project_id

  resources = {
    platform = "gpu-h100-sxm"
    preset   = "1gpu-16vcpu-200gb"
  }

  boot_disk = {
    attach_mode = "READ_WRITE"
    existing_disk = {
      id = nebius_compute_v1_disk.node1_disk.id
    }
  }

  network_interfaces = [
    {
      name              = "eth0"
      subnet_id         = var.subnet_id
      ip_address        = {}
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
          - ${file("../credentials/public_openssh.pub")}
  EOT
}

resource "nebius_compute_v1_instance" "node2" {
  name      = "h100-node2"
  parent_id = var.project_id

  resources = {
    platform = "gpu-h100-sxm"
    preset   = "1gpu-16vcpu-200gb"
  }

  boot_disk = {
    attach_mode = "READ_WRITE"
    existing_disk = {
      id = nebius_compute_v1_disk.node2_disk.id
    }
  }

  network_interfaces = [
    {
      name              = "eth0"
      subnet_id         = var.subnet_id
      ip_address        = {}
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
          - ${file("../credentials/public_openssh.pub")}
  EOT
}
