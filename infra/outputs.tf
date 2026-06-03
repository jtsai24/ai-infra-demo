output "node1_public_ip" {
  value = nebius_compute_v1_instance.node1.status.network_interfaces[0].public_ip_address.address
}

output "node2_public_ip" {
  value = nebius_compute_v1_instance.node2.status.network_interfaces[0].public_ip_address.address
}
