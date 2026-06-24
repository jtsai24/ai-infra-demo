#!/bin/bash
# Exp 3 Run B — INT4 GPTQ, gpu-memory-utilization 0.30, prefix caching OFF
# --served-model-name is kept as "qwen-7b" so load test scripts don't need to change.
# The actual model loaded is Qwen2.5-7B-Instruct-GPTQ-Int4 (--model flag).
kubectl delete pod -l app=vllm -n default
kubectl patch deployment vllm -n default --type=json -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/args",
   "value": [
     "--model", "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
     "--served-model-name", "qwen-7b",
     "--host", "0.0.0.0",
     "--port", "8000",
     "--gpu-memory-utilization", "0.30",
     "--quantization", "gptq",
     "--dtype", "float16",
     "--no-enable-prefix-caching"
   ]}
]'
sleep 5
kubectl logs -f deploy/vllm -n default