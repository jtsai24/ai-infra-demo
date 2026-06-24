#!/bin/bash
# Exp 4 Run A — chunked prefill OFF (degraded case), gpu-memory-utilization 0.70
# prefix caching ON (default) — multi-turn sessions stay decode-heavy
# inject prompts prepend unique ID to guarantee cache miss on every inject
kubectl delete pod -l app=vllm -n default
kubectl patch deployment vllm -n default --type=json -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/args",
   "value": [
     "--model", "Qwen/Qwen2.5-7B-Instruct",
     "--served-model-name", "qwen-7b",
     "--host", "0.0.0.0",
     "--port", "8000",
     "--gpu-memory-utilization", "0.70",
     "--no-enable-chunked-prefill",
     "--max-num-batched-tokens", "8192",
     "--max-model-len", "4096"
   ]}
]'
sleep 5
kubectl logs -f deploy/vllm -n default