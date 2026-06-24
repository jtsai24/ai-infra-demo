#!/bin/bash
NODE_IP=$1
MODEL="qwen-7b"

PROMPTS=(
  "What is attention in a transformer model?"
  "Explain CUDA cores vs tensor cores."
  "What does a GPU memory controller do?"
  "Describe the role of the KV cache in inference."
  "What is speculative decoding?"
)

for prompt in "${PROMPTS[@]}"; do
  echo "=== $prompt ==="
  curl -s http://$NODE_IP:30800/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d "{\"model\": \"$MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"$prompt\"}], \"max_tokens\": 200}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
  echo ""
done