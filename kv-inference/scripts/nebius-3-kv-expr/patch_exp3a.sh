#!/bin/bash
# Exp 3 Run A — bf16 baseline, gpu-memory-utilization 0.30, prefix caching OFF
kubectl delete pod -l app=vllm -n default
kubectl patch deployment vllm -n default --type=json -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/args",
   "value": [
     "--model", "Qwen/Qwen2.5-7B-Instruct",
     "--served-model-name", "qwen-7b",
     "--host", "0.0.0.0",
     "--port", "8000",
     "--gpu-memory-utilization", "0.30",
     "--no-enable-prefix-caching"
   ]}
]'
sleep 5
kubectl logs -f deploy/vllm -n default