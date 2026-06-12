# KV-Aware Inference Platform

Local inference benchmarks on MacBook Air M4 via Ollama, establishing baselines before moving to vLLM on Nebius in Phase 4.

## Setup

- **Model:** `qwen2.5:0.5b` (397MB, 4-bit quantized)
- **Hardware:** MacBook Air M4, 17.8GB unified memory, Metal GPU backend
- **Ollama:** 0.30.7
- **Server flags:** `OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0`

```bash
OLLAMA_FLASH_ATTENTION="1" OLLAMA_KV_CACHE_TYPE="q8_0" OLLAMA_NUM_PARALLEL=4 ollama serve
ollama pull qwen2.5:0.5b
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/measure_inference.py` | Single-request TTFT, TPOT, throughput via streaming API |
| `scripts/load_test.py` | Concurrent load test sweeping concurrency 1/2/4, reports TTFT p50/p95 |

## Benchmark Results

Raw output files in `benchmarks/local/`:
- [`benchmarks/local/measure_inference_cold_start.out`](benchmarks/local/measure_inference_cold_start.out) — first invocation, Metal cold start
- [`benchmarks/local/measure_inference_warm.out`](benchmarks/local/measure_inference_warm.out) — second invocation, fully warm
- [`benchmarks/local/load_test_num_parallel_1.out`](benchmarks/local/load_test_num_parallel_1.out) — load test, sequential queuing
- [`benchmarks/local/load_test_num_parallel_4.out`](benchmarks/local/load_test_num_parallel_4.out) — load test, 4 concurrent slots
- [`benchmarks/local/load_test_num_parallel_8.out`](benchmarks/local/load_test_num_parallel_8.out) — load test, 8 concurrent slots

### Single request (`measure_inference.py`, `NUM_PARALLEL=1`)

| Run | TTFT | TPOT | Throughput | Tokens |
|-----|------|------|------------|--------|
| 1st invocation (post-warmup) | 964.5ms | 13.1 ms/token | 55.1 tok/s | 188 |
| 2nd invocation (fully warm) | 127.8ms | 13.6 ms/token | 69.3 tok/s | 134 |

The `ollama run warmup` loads weights but Metal buffer allocation happens on first HTTP API call — always discard the first script run.

### Load test (`load_test.py`)

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

## Analysis

**Bottleneck is compute, not memory.**
- Model weights + 4 KV cache slots ≈ ~700MB of 17.8GB — memory is not the constraint
- M4 GPU matrix multiply throughput is the ceiling
- `NUM_PARALLEL` allocates KV cache slots and time-slices GPU compute across them — it is not true hardware parallelism
- More slots → lower TTFT (less queuing), lower throughput per request (compute divided more ways)

**Scaling requires more hardware.**
- 2x GPU compute → 2x concurrent requests at the same per-request throughput
- A100 on Nebius (~30x M4's ~10 TFLOPS) sustains much higher concurrency before saturation
- Multi-GPU tensor parallelism is how production systems scale beyond a single GPU

## Portfolio Context

These numbers are the local baseline to compare against vLLM on Nebius in Phase 4. vLLM with continuous batching dynamically manages request batching based on available GPU memory rather than a fixed slot count — critical for large models (e.g. 70B on 40GB A100) where memory is the binding constraint. The gap between these Ollama/M4 numbers and vLLM/Nebius numbers is part of the portfolio story.