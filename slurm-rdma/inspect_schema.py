import json, sys

s = json.load(sys.stdin)
resource = s['provider_schemas']['registry.terraform.io/nebius/nebius']['resource_schemas']['nebius_compute_v1_instance']
print(json.dumps(resource, indent=2))
