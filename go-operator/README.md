# Go Kubernetes Operator — vLLM Autoscaler

A custom Kubernetes operator (Go, kubebuilder) that watches a `WorkloadLifecycle` custom resource, polls a vLLM deployment's KV cache usage via a metrics endpoint, and scales the deployment's replica count within configured bounds — a hysteresis band between the scale-up and scale-down thresholds prevents flapping at the boundary.

## What this demonstrates

- Kubebuilder project scaffolding: CRD types, controller, RBAC markers, manifest generation (`make manifests`/`make generate`)
- CRD schema design: kubebuilder validation markers, the implicit-required-field behavior of `controller-gen` (a field is required unless its json tag carries `omitempty`), and why `float64` fields are rejected in favor of `int32` percentages
- A `MetricsProvider` interface decoupling the reconciler from where metrics come from (HTTP stub today, Prometheus later)
- Polling-based reconciliation (`RequeueAfter`) vs. push/event-driven reconciliation, and the difference between in-cluster DNS and host-machine networking (`kubectl port-forward`)
- A real architectural bug found and fixed: a metrics provider built once in `main.go` can't reflect per-CR configuration — fixed by reading `wl.Spec` fresh on every reconcile
- Splitting a flat `Reconcile` function into per-concern helpers (`observeMetrics`, `observeDeployment`, `computeDesiredReplicas`, `makeAdjustmentIfNeeded`) so each sits at one abstraction level
- `.status` subresource writeback: current-observation fields (`ObservedKVCacheUsagePercent`, `DesiredReplicas`, `LastScaleTime`, `LastTransitionReason`) plus standard `Available`/`Degraded` Conditions via `meta.SetStatusCondition`, written through `r.Status().Update()` (not `r.Update()`) at every reconcile exit path
- A second real bug found and fixed: status writes re-triggering the controller's own watch, causing overlapping reconciles and an intermittent `409 Conflict` on the Deployment patch — fixed by adding `predicate.GenerationChangedPredicate{}` to the watch, since `.metadata.generation` only bumps on `.spec` writes, never on `.status`-only writes
- Kubernetes Events (`EventRecorder`) as the history-log counterpart to `.status`'s current-snapshot: `Warning`/`Normal` events gated on reason-change rather than firing every reconcile, to avoid flooding `kubectl describe` on a sustained failure

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

## Status & Events

`kubectl describe workloadlifecycle` now shows two complementary things: `.status` (a snapshot of the most recent observation and decision) and `Events` (a history of what actually happened). Verified live across every reachable exit scenario except one — forcing a genuine Deployment-patch conflict deterministically requires a fake client with error injection rather than manual triggering (deferred to a future unit test suite). Raw test output and command sequences in [#19](https://github.com/jtsai24/ai-infra-demo/issues/19) and [#20](https://github.com/jtsai24/ai-infra-demo/issues/20).

```
Status:
  Conditions:
    Reason:                          Holding
    Status:                          True
    Type:                            Available
  Desired Replicas:                  1
  Last Scale Time:                   2026-08-07T20:00:35Z
  Last Transition Reason:            Holding
  Observed Kv Cache Usage Percent:   15
Events:
  Type     Reason              Age    Message
  ----     ------              ----   -------
  Normal   ScaledUp            5m25s  Scaled mock-vllm from 1 to 2 replicas (KV cache 85% vs threshold 80%)
  Normal   ScaledUp            5m10s  Scaled mock-vllm from 2 to 3 replicas (KV cache 85% vs threshold 80%)
  Warning  MetricsUnavailable  3m40s  calling metrics endpoint: dial tcp [::1]:8080: connect: connection refused
  Normal   Recovered           3m10s  recovered from MetricsUnavailable
  Normal   ScaledDown          55s    Scaled mock-vllm from 3 to 2 replicas (KV cache 15% vs threshold 25%)
  Normal   ScaledDown          40s    Scaled mock-vllm from 2 to 1 replicas (KV cache 15% vs threshold 25%)
```

Confirmed correct, including the parts that are easy to get subtly wrong:
- A sustained failure (metrics-stub unreachable for multiple reconcile cycles, or `spec.targetDeployment` pointed at a nonexistent name) produces exactly **one** `Warning` event, not one per 15s tick — gated by comparing the failure reason against the last reconcile's recorded reason, not a boolean "is it degraded" flip
- `Recovered` correctly names which specific failure it recovered from (`MetricsUnavailable` vs. `TargetDeploymentNotFound`), confirming the recovery check distinguishes between them rather than firing on any `Degraded → healthy` transition
- Recovering from a scale failure does *not* get its own `Recovered` event — the `ScaledUp`/`ScaledDown` event that follows already reports it, avoiding a double-announcement of the same occurrence
- Conditions' `LastTransitionTime` only moves when `Status` (True/False) itself flips, not on every reconcile — confirmed unchanged across several `Holding ↔ ScaledUp/ScaledDown` transitions where only `Reason` changed

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
| 9 | `.status` writeback + fix self-triggering reconcile loop | [#19](https://github.com/jtsai24/ai-infra-demo/issues/19) |
| 10 | `EventRecorder` — Warning/Normal events for observation and scaling outcomes | [#20](https://github.com/jtsai24/ai-infra-demo/issues/20) |

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
- `.status` is a separate API subresource from `.spec` for a reason: it's written only by the controller (via `r.Status().Update()`), never by users, and has its own RBAC verbs (`workloadlifecycles/status`) distinct from the main resource
- `meta.SetStatusCondition` does not auto-populate `ObservedGeneration` — it copies whatever value you pass on the `Condition` literal, so it silently stays `0` forever unless set explicitly to `wl.Generation` on every call
- A controller's own `.status` writes can retrigger its own watch and cause a self-inflicted reconcile storm, since controller-runtime's default watch doesn't distinguish "spec changed" from "status changed" — `predicate.GenerationChangedPredicate{}` is the fix, since `.metadata.generation` only moves on `.spec` edits
- `.status` and Events answer different questions and shouldn't be updated on the same cadence: status reflects "what's true right now" (updated every valid reconcile, including no-ops, since that's the liveness signal), Events reflect "what happened, when" (only on transitions/discrete actions — emitting on every tick would flood `kubectl describe` even with Kubernetes' own event dedup)

## Not yet started

- Unit tests (fake client + interceptor) — no test suite exists yet; motivated by needing to deterministically verify a Deployment-patch conflict (`ScaleFailed`) without relying on live-cluster timing races
- Xid cordon/drain action
- Metric-gated rollback action
- Deployment against a real Nebius H100 cluster with an actual vLLM instance behind the operator
