#!/bin/bash
# Exp 4 Run B — chunked prefill ON (vLLM V1 default), gpu-memory-utilization 0.70
# prefix caching ON (default) — multi-turn sessions stay decode-heavy
kubectl delete pod -l app=vllm -n default
kubectl patch deployment vllm -n default --type=json -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/args",
   "value": [
     "--model", "Qwen/Qwen2.5-7B-Instruct",
     "--served-model-name", "qwen-7b",
     "--host", "0.0.0.0",
     "--port", "8000",
     "--gpu-memory-utilization", "0.70",
     "--max-num-batched-tokens", "512"
   ]}
]'
sleep 5
kubectl logs -f deploy/vllm -n default