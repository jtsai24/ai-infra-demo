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

resource "nebius_compute_v1_instance" "cpu_validation" {
  name      = "cpu-validation"
  parent_id = var.project_id

  resources = {
    platform = "cpu-e2"
    preset   = "2vcpu-8gb"
  }

  boot_disk = {
    attach_mode = "READ_WRITE"
    managed_disk = {
      name = "cpu-validation-disk"
      spec = {
        source_image_id = "computeimage-e00x8tej7rj2bpm8pk"
        size_gibibytes  = 20
        type            = "NETWORK_SSD"
      }
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
          - ${file("credentials/public_openssh.pub")}
  EOT
}
