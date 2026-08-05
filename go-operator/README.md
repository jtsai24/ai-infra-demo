# Go Kubernetes Operator — vLLM Autoscaler

A custom Kubernetes operator (Go, kubebuilder) that watches a `WorkloadLifecycle` custom resource, polls a vLLM deployment's KV cache usage via a metrics endpoint, and scales the deployment's replica count within configured bounds — a hysteresis band between the scale-up and scale-down thresholds prevents flapping at the boundary.

## What this demonstrates

- Kubebuilder project scaffolding: CRD types, controller, RBAC markers, manifest generation (`make manifests`/`make generate`)
- CRD schema design: kubebuilder validation markers, the implicit-required-field behavior of `controller-gen` (a field is required unless its json tag carries `omitempty`), and why `float64` fields are rejected in favor of `int32` percentages
- A `MetricsProvider` interface decoupling the reconciler from where metrics come from (HTTP stub today, Prometheus later)
- Polling-based reconciliation (`RequeueAfter`) vs. push/event-driven reconciliation, and the difference between in-cluster DNS and host-machine networking (`kubectl port-forward`)
- A real architectural bug found and fixed: a metrics provider built once in `main.go` can't reflect per-CR configuration — fixed by reading `wl.Spec` fresh on every reconcile
- Splitting a flat `Reconcile` function into per-concern helpers (`observeMetrics`, `observeDeployment`, `computeDesiredReplicas`, `makeAdjustmentIfNeeded`) so each sits at one abstraction level

## Local dev environment

Built and validated entirely without a real vLLM instance or GPU spend:

- **`mock-vllm`** — an `nginx:alpine` Deployment standing in for vLLM. The operator only ever acts on `spec.replicas`, so the actual served content is irrelevant.
- **`metrics-stub`** — a small Flask app faking a Prometheus-style `/metrics` endpoint, with a `/set` endpoint to inject KV cache usage values at runtime and watch the operator react.

Both run as pods in a local OrbStack Kubernetes cluster, giving near copy-paste manifests for a later deployment against a real Nebius cluster.

## How it works

```
WorkloadLifecycle CR  →  MetricsProvider.GetMetrics()  →  compare vs. thresholds  →  patch Deployment.Spec.Replicas
     (spec: thresholds,        (HTTP GET, parses               (hysteresis band:            (r.Update, full-object
      target deployment,        Prometheus text format)          scale up / hold /            patch, re-polled every
      metrics endpoint)                                          scale down)                  RequeueAfter)
```

Every reconcile re-fetches the CR and rebuilds a fresh `MetricsProvider` from its spec — correctly scoped per-CR (multiple `WorkloadLifecycle` objects, each targeting a different deployment, work without any shared mutable state) while still reusing a single pooled `http.Client` for connection efficiency.

## Results

Verified live against a running cluster (`mock-vllm` + `metrics-stub`, OrbStack Kubernetes), driving KV cache usage through all three control regions and confirming two independent sources agree at every step: operator logs and `kubectl get deploy -w`. Raw test output in [#16](https://github.com/jtsai24/ai-infra-demo/issues/16).

| KV cache usage | Region | Action | Replicas |
|---|---|---|---|
| 85% | Above `KVCacheThresholdPercent` (80%) | Scale up, capped at `MaxReplicas` | 1 → 2 → 3 (holds at 3) |
| 15% | Below `KVCacheScaleDownThresholdPercent` (25%) | Scale down, floored at `MinReplicas` | 3 → 2 → 1 (holds at 1) |
| 50% | Inside the 25–80% hysteresis band | Hold steady, no flapping | unchanged |

```
observed metrics    kvCacheUsagePercent=85 numRequestsWaiting=5
scaling decision     currentReplicas=1 desiredReplicas=2 ...
scaling decision     currentReplicas=2 desiredReplicas=3 ...
no scaling action needed   currentReplicas=3 kvCacheUsagePercent=85 ...  (capped)
```

Driven via the metrics-stub's `/set` endpoint mid-run, with no restart of `make run` between changes — confirming CR-driven fetching, connection reuse, and live metric changes all work correctly together.

## Development log

| Stage | What | Issue |
|---|---|---|
| 1 | `mock-vllm` Deployment manifest + validation | [#10](https://github.com/jtsai24/ai-infra-demo/issues/10) |
| 2 | Flask metrics-stub — `/metrics` + `/set` | [#11](https://github.com/jtsai24/ai-infra-demo/issues/11) |
| 3 | Containerize + deploy metrics-stub to Kubernetes | [#12](https://github.com/jtsai24/ai-infra-demo/issues/12) |
| 4 | `WorkloadLifecycle` CRD types + `MetricsProvider` | [#13](https://github.com/jtsai24/ai-infra-demo/issues/13) |
| 5 | Wire `Reconcile` to `MetricsProvider`, log observed metrics | [#14](https://github.com/jtsai24/ai-infra-demo/issues/14) |
| 6 | Scale-up decision + Deployment patch | [#15](https://github.com/jtsai24/ai-infra-demo/issues/15) |
| 7 | Scale-down threshold — hysteresis band | [#16](https://github.com/jtsai24/ai-infra-demo/issues/16) |
| 8 | Refactor `Reconcile` into per-concern helpers | [#17](https://github.com/jtsai24/ai-infra-demo/issues/17) |

Full tracking issue with build order and status: [#18](https://github.com/jtsai24/ai-infra-demo/issues/18)

## Repo layout

```
go-operator/
  api/v1alpha1/                 WorkloadLifecycle CRD types
  internal/controller/          Reconcile loop, MetricsProvider
  config/crd, config/rbac, ...  kubebuilder-generated manifests
  local-test/                   mock-vllm manifest, metrics-stub (Flask app + Dockerfile)
```

## Key lessons learned

- `controller-gen` rejects `float64` fields ("highly discouraged... support varies across languages") — use scaled integers instead, matching real Kubernetes API conventions (e.g. HPA's `averageUtilization`)
- A Go struct field becomes required in the generated CRD schema by default; `omitempty` (not a `+kubebuilder:validation:Required` marker) is what makes it optional
- `metrics-stub`'s `ClusterIP` Service is only reachable from inside the cluster — `make run` executes the operator on the host machine, not in-cluster, so it needs `kubectl port-forward` to reach it, exactly like a manual `curl` test would
- Reconciliation is polling, not push — an external metric changing triggers nothing on its own; `RequeueAfter` is what drives repeated observation
- A single global cache for the metrics provider would be actively wrong once more than one CR exists (each needs independently-tracked config, concurrent reconciles would race on shared state) — building a fresh provider per reconcile while sharing only the pooled `http.Client` is both simpler and correct for any number of CRs

## Not yet started

- Status writeback on the CR (cross-cutting)
- Xid cordon/drain action
- Metric-gated rollback action
- Deployment against a real Nebius H100 cluster with an actual vLLM instance behind the operator
