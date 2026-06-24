# KV-Aware Inference Platform

vLLM inference platform with full observability. Local validation on MacBook Air M4 (Ollama and vLLM-metal), then deployed on Nebius H100 in staged sessions.

---

## Local — MacBook Air M4

### Setup

#### Ollama
- **Model:** `qwen2.5:0.5b` (397MB, 4-bit quantized)
- **Hardware:** MacBook Air M4, 17.8GB unified memory, Metal GPU backend
- **Ollama:** 0.30.7
- **Server flags:** `OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0`

```bash
OLLAMA_FLASH_ATTENTION="1" OLLAMA_KV_CACHE_TYPE="q8_0" OLLAMA_NUM_PARALLEL=4 ollama serve
ollama pull qwen2.5:0.5b
```

#### vLLM-metal
- **Model:** `mlx-community/Qwen2.5-0.5B-Instruct-4bit`
- **vLLM-metal:** 0.3.0, Metal GPU backend via MLX
- **Install:** `curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash`

```bash
source ~/.venv-vllm-metal/bin/activate
vllm serve mlx-community/Qwen2.5-0.5B-Instruct-4bit --port 8000
```

### Scripts

#### Ollama
| Script | Purpose |
|--------|---------|
| `scripts/measure_inference_ollama.py` | Single-request TTFT, TPOT, throughput via streaming API |
| `scripts/load_test_ollama.py` | Concurrent load test sweeping concurrency 1/2/4, reports TTFT p50/p95 |

#### vLLM
| Script | Purpose |
|--------|---------|
| `scripts/measure_inference_vllm.py` | Single-request TTFT, TPOT, throughput via streaming API |
| `scripts/load_test_vllm.py` | Concurrent load test sweeping concurrency 1/2/4, reports TTFT p50/p95 |

### Results

#### Ollama

Raw output: [`benchmarks/local/ollama/`](benchmarks/local/ollama/)
- [`measure_inference_cold_start.out`](benchmarks/local/ollama/measure_inference_cold_start.out) — first invocation, Metal cold start
- [`measure_inference_warm.out`](benchmarks/local/ollama/measure_inference_warm.out) — second invocation, fully warm
- [`load_test_num_parallel_1.out`](benchmarks/local/ollama/load_test_num_parallel_1.out) — load test, sequential queuing
- [`load_test_num_parallel_4.out`](benchmarks/local/ollama/load_test_num_parallel_4.out) — load test, 4 concurrent slots
- [`load_test_num_parallel_8.out`](benchmarks/local/ollama/load_test_num_parallel_8.out) — load test, 8 concurrent slots

##### Single request (`measure_inference_ollama.py`, `NUM_PARALLEL=1`)

| Run | TTFT | TPOT | Throughput | Tokens |
|-----|------|------|------------|--------|
| 1st invocation (post-warmup) | 964.5ms | 13.1 ms/token | 55.1 tok/s | 188 |
| 2nd invocation (fully warm) | 127.8ms | 13.6 ms/token | 69.3 tok/s | 134 |

The `ollama run warmup` loads weights but Metal buffer allocation happens on first HTTP API call — always discard the first script run.

##### Load test (`load_test_ollama.py`)

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

##### Ollama analysis

- Model weights + 4 KV cache slots ≈ ~700MB of 17.8GB — memory is not the constraint
- M4 GPU matrix multiply throughput is the ceiling
- `NUM_PARALLEL` allocates KV cache slots and time-slices GPU compute — not true hardware parallelism
- More slots → lower TTFT (less queuing), lower throughput per request (compute divided more ways)

---

#### vLLM-metal

Raw output: [`benchmarks/local/vllm/`](benchmarks/local/vllm/)
- [`measure_inference_cold_to_warm.out`](benchmarks/local/vllm/measure_inference_cold_to_warm.out) — 3 runs showing warmup progression
- [`load_test_default_max_num_seqs.out`](benchmarks/local/vllm/load_test_default_max_num_seqs.out) — load test, default `--max-num-seqs=256`
- [`load_test_max_num_seqs_1.out`](benchmarks/local/vllm/load_test_max_num_seqs_1.out) — load test, `--max-num-seqs=1` (sequential queuing)

See [`benchmarks/local/vllm/DISCUSSION.md`](benchmarks/local/vllm/DISCUSSION.md) for full analysis.

##### Single request (`measure_inference_vllm.py`, default `--max-num-seqs=256`)

| Run | TTFT | TPOT | Throughput | Tokens |
|-----|------|------|------------|--------|
| 1 (cold) | 6,997ms | 9.7 ms/token | 20.1 tok/s | 174 |
| 2 | 2,071ms | 9.0 ms/token | 51.7 tok/s | 200 |
| 3 (warm) | 1,980ms | 9.1 ms/token | 52.8 tok/s | 200 |

vLLM has more warmup overhead than Ollama — stabilizes at ~2 seconds TTFT vs Ollama's ~128ms. Higher baseline TTFT is due to vLLM's scheduler overhead.

##### Load test (`load_test_vllm.py`)

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

##### vLLM analysis

- `--max-num-seqs` is vLLM's equivalent of Ollama's `OLLAMA_NUM_PARALLEL`
- vLLM's continuous batching actively improves TTFT under load by batching requests into a single GPU forward pass
- Ollama time-slices without true batching — TTFT always degrades with concurrency
- Higher single-request TTFT on vLLM (~2s vs ~128ms) is the cost of the more complex scheduler

---

## Nebius — H100

### Stage 1: nebius-vllm-only

Runbook: [`runbooks/nebius-vllm-only-apply.md`](runbooks/nebius-vllm-only-apply.md)
Infra: [`infra/nebius-vllm-only/`](infra/nebius-vllm-only/)

**What this stage de-risks:**
- Nebius managed k8s cluster provisioning via Terraform two-step apply
- vLLM pod deployment on a real H100 SXM node
- OpenAI-compatible API reachable via `kubectl exec`
- All three operator target metrics confirmed live on `/metrics` before building the operator

**Hardware:** 1× H100 SXM (`1gpu-16vcpu-200gb`), vLLM `0.23.0`, `Qwen/Qwen2.5-0.5B-Instruct`

**Status:** Complete. Observability stack deployed and validated in Stage 2.

---

### Stage 2: nebius-2-vllm-w-observ

Runbook: [`runbooks/nebius-2-vllm-w-observ-apply.md`](runbooks/nebius-2-vllm-w-observ-apply.md)
Infra: [`infra/nebius-2-vllm-w-observ/`](infra/nebius-2-vllm-w-observ/)

**What this stage adds:**
- Prometheus, Loki, Promtail, Grafana deployed via Helm into the same cluster as vLLM
- Prometheus scraping vLLM `/metrics` endpoint confirmed live
- Loki log pipeline confirmed: Promtail collecting pod logs → Loki ingesting → Grafana queryable
- Grafana dashboard with vLLM metrics and log panels (`nebius-vllm-dashboard.json`)

**Hardware:** 1× H100 SXM (`1gpu-16vcpu-200gb`), vLLM `0.23.0`, `Qwen/Qwen2.5-0.5B-Instruct`

**Nebius H100 single-request results (`measure_inference_vllm.py`):**

| Run | TTFT | TPOT | Throughput | Tokens |
|-----|------|------|------------|--------|
| Warm | 366ms | 1.8 ms/token | 278 tok/s | 200 |

H100 TPOT (1.8ms) is 5× faster than M4 (9.1ms). TTFT (366ms warm) is higher than M4 (1,980ms) — H100 runs the full-precision model vs M4's 4-bit quantized MLX build; prefill is proportionally more expensive.

**KV cache pressure:** Not observed at concurrency 1–4 with Qwen2.5-0.5B. The model's KV cache footprint (~200MB) is negligible against the H100's 80GB HBM. A larger model (Llama 3 8B or 70B) at high concurrency with long context would be required to generate measurable cache pressure.

**Status:** Complete. Observability pipeline validated end-to-end.

---

### Stage 3: nebius-3-kv-expr

Infra: [`infra/nebius-3-kv-expr/`](infra/nebius-3-kv-expr/)

**What this stage adds:**
- Upgraded model to `Qwen/Qwen2.5-7B-Instruct` (bf16) — large enough for KV cache pressure to be the binding constraint
- Four controlled experiments varying one vLLM config lever at a time, each with a kubectl patch script
- Load generators: `ramp_load_test.py` (concurrency ramp 8→16→24) and `load_test_chunked_prefill.py` (multi-turn + injector thread)
- HuggingFace model cache persisted across pod restarts via hostPath volume — eliminates re-download between experiment runs

**Hardware:** 1× H100 SXM (`1gpu-16vcpu-200gb`), vLLM V1, `Qwen/Qwen2.5-7B-Instruct`

**Experiments:**

| Experiment | Variable | Key Finding | Issue |
|---|---|---|---|
| [Exp 1 — KV Cache Size vs Throughput](https://github.com/jtsai24/ai-infra-demo/issues/5) | `gpu_memory_utilization` 0.30 vs 0.70 | At 0.30, KV cache hit 100% and TTFT p95 climbed to ~6s with ~8 requests queued; at 0.70, queue stayed at 0 and TTFT p95 ~3.5s | #5 |
| [Exp 2 — Prefix Caching](https://github.com/jtsai24/ai-infra-demo/issues/7) | Prefix cache OFF vs ON | Enabling prefix cache cut TTFT p95 **10×** (4–5s → 0.4–0.5s) and halved KV cache consumption under multi-turn load | #7 |
| [Exp 3 — Weight Quantization](https://github.com/jtsai24/ai-infra-demo/issues/8) | bf16 vs INT4 GPTQ | INT4 weights 2.6× smaller (14GB → 5.3GB), freed 50% more KV cache headroom, TPOT improved 27%, 38% more requests completed in same window | #8 |
| [Exp 4 — Chunked Prefill](https://github.com/jtsai24/ai-infra-demo/issues/9) | Chunked prefill OFF vs ON | Without chunking, a 2000-token inject caused 10–15× TPOT spikes (6ms → 50–93ms) in concurrent decode sessions; chunking eliminated all spikes | #9 |

**Scripts:**

| Script | Purpose |
|---|---|
| `scripts/nebius-3-kv-expr/ramp_load_test.py` | Concurrency ramp 8→16→24, configurable stage duration |
| `scripts/nebius-3-kv-expr/load_test_chunked_prefill.py` | 4 multi-turn sessions + injector thread firing ~2000-token cold prompts every 15s |
| `scripts/nebius-3-kv-expr/patch_exp2a.sh` / `patch_exp2b.sh` | kubectl patches for Exp 2 (prefix caching OFF vs ON) |
| `scripts/nebius-3-kv-expr/patch_exp3a.sh` / `patch_exp3b.sh` | kubectl patches for Exp 3 (bf16 vs INT4 GPTQ) |
| `scripts/nebius-3-kv-expr/patch_exp4a.sh` / `patch_exp4b.sh` | kubectl patches for Exp 4 (chunked prefill OFF vs ON) |

**Raw benchmark outputs:** [`benchmarks/nebius-3-kv-expr/`](benchmarks/nebius-3-kv-expr/)

**Status:** Complete.

---

## Tradeoffs & Known Limitations

**Why Terraform over Pulumi:** Terraform's declarative model does not natively support imperative ordering of side effects. The Nebius managed Kubernetes provider writes cluster credentials to `~/.kube/config` via a CLI command (`nebius mk8s v1 cluster get-credentials`) rather than emitting ExecCredential JSON to stdout, which means the kubeconfig population cannot be expressed as a Terraform resource. This forces a manual step between Stage 1 (cluster + node group) and Stage 2 (Kubernetes + Helm resources), breaking the single-apply declarative model. Nebius provides an official Pulumi provider that would solve this cleanly — since Pulumi uses real Go/Python code, the credential fetch can be expressed as a regular function call with explicit ordering, enabling a single `pulumi up` with no manual intervention. Terraform was chosen here for portfolio visibility given its dominance in AI infra shops, but this is the concrete cost of that choice.

---

## Portfolio Context

Local results establish the baseline pattern. The real story plays out on Nebius with an H100 and Llama 3 8B, where KV cache memory pressure and continuous batching tradeoffs become the binding constraints — not GPU compute headroom as on the M4. vLLM with continuous batching dynamically manages request batching based on available GPU memory rather than a fixed slot count, which is critical for large models where memory is the constraint. The gap between local and Nebius numbers is part of the portfolio story.