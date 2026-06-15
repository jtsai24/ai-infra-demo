# KV-Aware Inference Platform

Local inference benchmarks on MacBook Air M4, establishing baselines before moving to vLLM on Nebius in Phase 4. Two inference backends tested locally: Ollama (Metal GPU) and vLLM-metal.

## Setup

### Ollama
- **Model:** `qwen2.5:0.5b` (397MB, 4-bit quantized)
- **Hardware:** MacBook Air M4, 17.8GB unified memory, Metal GPU backend
- **Ollama:** 0.30.7
- **Server flags:** `OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0`

```bash
OLLAMA_FLASH_ATTENTION="1" OLLAMA_KV_CACHE_TYPE="q8_0" OLLAMA_NUM_PARALLEL=4 ollama serve
ollama pull qwen2.5:0.5b
```

### vLLM-metal
- **Model:** `mlx-community/Qwen2.5-0.5B-Instruct-4bit`
- **vLLM-metal:** 0.3.0, Metal GPU backend via MLX
- **Install:** `curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash`

```bash
source ~/.venv-vllm-metal/bin/activate
vllm serve mlx-community/Qwen2.5-0.5B-Instruct-4bit --port 8000
```

## Scripts

### Ollama
| Script | Purpose |
|--------|---------|
| `scripts/measure_inference_ollama.py` | Single-request TTFT, TPOT, throughput via streaming API |
| `scripts/load_test_ollama.py` | Concurrent load test sweeping concurrency 1/2/4, reports TTFT p50/p95 |

### vLLM
| Script | Purpose |
|--------|---------|
| `scripts/measure_inference_vllm.py` | Single-request TTFT, TPOT, throughput via streaming API |
| `scripts/load_test_vllm.py` | Concurrent load test sweeping concurrency 1/2/4, reports TTFT p50/p95 |

---

## Local Results — MacBook Air M4

### Ollama

Raw output: [`benchmarks/local/ollama/`](benchmarks/local/ollama/)
- [`measure_inference_cold_start.out`](benchmarks/local/ollama/measure_inference_cold_start.out) — first invocation, Metal cold start
- [`measure_inference_warm.out`](benchmarks/local/ollama/measure_inference_warm.out) — second invocation, fully warm
- [`load_test_num_parallel_1.out`](benchmarks/local/ollama/load_test_num_parallel_1.out) — load test, sequential queuing
- [`load_test_num_parallel_4.out`](benchmarks/local/ollama/load_test_num_parallel_4.out) — load test, 4 concurrent slots
- [`load_test_num_parallel_8.out`](benchmarks/local/ollama/load_test_num_parallel_8.out) — load test, 8 concurrent slots

#### Single request (`measure_inference_ollama.py`, `NUM_PARALLEL=1`)

| Run | TTFT | TPOT | Throughput | Tokens |
|-----|------|------|------------|--------|
| 1st invocation (post-warmup) | 964.5ms | 13.1 ms/token | 55.1 tok/s | 188 |
| 2nd invocation (fully warm) | 127.8ms | 13.6 ms/token | 69.3 tok/s | 134 |

The `ollama run warmup` loads weights but Metal buffer allocation happens on first HTTP API call — always discard the first script run.

#### Load test (`load_test_ollama.py`)

**`NUM_PARALLEL=1` — sequential queuing:**

| Concurrency | TTFT p50 | TTFT p95 | Throughput/req |
|-------------|----------|----------|----------------|
| 1 | 961ms | 961ms | 54 tok/s |
| 2 | 3,300ms | 6,438ms | 56 tok/s |
| 4 | 7,238ms | 18,176ms | 42 tok/s |

TTFT degrades linearly — requests queue. Throughput stays flat — GPU never idle.

**`NUM_PARALLEL=4` — concurrent slots:**

| Concurrency | TTFT p50 | TTFT p95 | Throughput/req |
|-------------|----------|----------|----------------|
| 1 | 680ms | 680ms | 59 tok/s |
| 2 | 171ms | 171ms | 114 tok/s |
| 4 | 252ms | 286ms | 64 tok/s |

Sweet spot at concurrency 2. At concurrency 4, GPU compute is saturated.

**`NUM_PARALLEL=8`:** Essentially identical to `NUM_PARALLEL=4` — load test only reaches concurrency 4 so extra slots go unused.

#### Ollama analysis

- Model weights + 4 KV cache slots ≈ ~700MB of 17.8GB — memory is not the constraint
- M4 GPU matrix multiply throughput is the ceiling
- `NUM_PARALLEL` allocates KV cache slots and time-slices GPU compute — not true hardware parallelism
- More slots → lower TTFT (less queuing), lower throughput per request (compute divided more ways)

---

### vLLM-metal

Raw output: [`benchmarks/local/vllm/`](benchmarks/local/vllm/)
- [`measure_inference_cold_to_warm.out`](benchmarks/local/vllm/measure_inference_cold_to_warm.out) — 3 runs showing warmup progression
- [`load_test_default_max_num_seqs.out`](benchmarks/local/vllm/load_test_default_max_num_seqs.out) — load test, default `--max-num-seqs=256`
- [`load_test_max_num_seqs_1.out`](benchmarks/local/vllm/load_test_max_num_seqs_1.out) — load test, `--max-num-seqs=1` (sequential queuing)

See [`benchmarks/local/vllm/DISCUSSION.md`](benchmarks/local/vllm/DISCUSSION.md) for full analysis.

#### Single request (`measure_inference_vllm.py`, default `--max-num-seqs=256`)

| Run | TTFT | TPOT | Throughput | Tokens |
|-----|------|------|------------|--------|
| 1 (cold) | 6,997ms | 9.7 ms/token | 20.1 tok/s | 174 |
| 2 | 2,071ms | 9.0 ms/token | 51.7 tok/s | 200 |
| 3 (warm) | 1,980ms | 9.1 ms/token | 52.8 tok/s | 200 |

vLLM has more warmup overhead than Ollama — stabilizes at ~2 seconds TTFT vs Ollama's ~128ms. Higher baseline TTFT is due to vLLM's scheduler overhead.

#### Load test (`load_test_vllm.py`)

**Default `--max-num-seqs=256` — continuous batching:**

| Concurrency | TTFT p50 | TTFT p95 | Throughput/req |
|-------------|----------|----------|----------------|
| 1 | 1,968ms | 1,968ms | 54 tok/s |
| 2 | 211ms | 336ms | 74 tok/s |
| 4 | 106ms | 106ms | 74 tok/s |

TTFT improves as concurrency increases — opposite of Ollama. Continuous batching amortizes scheduler overhead across all requests in the batch (bus effect).

**`--max-num-seqs=1` — sequential queuing:**

| Concurrency | TTFT p50 | TTFT p95 | Throughput/req |
|-------------|----------|----------|----------------|
| 1 | 3,490ms | 3,490ms | 38 tok/s |
| 2 | 1,129ms | 2,171ms | 71 tok/s |
| 4 | 2,901ms | 5,649ms | 55 tok/s |

TTFT degrades with concurrency, mirroring Ollama `NUM_PARALLEL=1`. Concurrency 2 still better than concurrency 1 due to vLLM's internal scheduler behavior.

#### vLLM analysis

- `--max-num-seqs` is vLLM's equivalent of Ollama's `OLLAMA_NUM_PARALLEL`
- vLLM's continuous batching actively improves TTFT under load by batching requests into a single GPU forward pass
- Ollama time-slices without true batching — TTFT always degrades with concurrency
- Higher single-request TTFT on vLLM (~2s vs ~128ms) is the cost of the more complex scheduler

---

## Nebius H100 Results

**Session 1 — Single H100 SXM, `Qwen/Qwen2.5-0.5B-Instruct`**

- Provisioned via Terraform: Nebius managed k8s cluster, 1× H100 SXM node (`1gpu-16vcpu-200gb`)
- vLLM `0.23.0` deployed as a Kubernetes pod, serving the OpenAI-compatible API on port 8000
- Inference validated end-to-end via `kubectl exec`
- All three operator target metrics confirmed live on `/metrics`:
  - `vllm:kv_cache_usage_perc`
  - `vllm:num_requests_running`
  - `vllm:num_requests_waiting`

Full observability stack and load test results to be added in Session 2.

---

## Portfolio Context

Local results establish the baseline pattern. The real story plays out on Nebius with an H100 and Llama 3 8B, where KV cache memory pressure and continuous batching tradeoffs become the binding constraints — not GPU compute headroom as on the M4. vLLM with continuous batching dynamically manages request batching based on available GPU memory rather than a fixed slot count, which is critical for large models where memory is the constraint. The gap between local and Nebius numbers is part of the portfolio story.