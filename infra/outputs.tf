output "public_ip" {
  value = nebius_compute_v1_instance.cpu_validation.status.network_interfaces[0].public_ip_address.address
}
