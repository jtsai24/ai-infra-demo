package controller

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
)

// Metrics holds the values the reconciler cares about, independent of
// where they came from (HTTP stub today, Prometheus later).
type Metrics struct {
	KVCacheUsagePercent int32 // 0-100, matches WorkloadLifecycleSpec.KVCacheThresholdPercent
	NumRequestsWaiting  int32
}

// MetricsProvider abstracts metrics access away from reconcile logic.
// The reconciler consumes this interface without knowing whether values
// come from a Flask stub, Prometheus, or a fake used in tests.
type MetricsProvider interface {
	GetMetrics(ctx context.Context) (Metrics, error)
}

// HTTPMetricsProvider reads metrics from the metrics-stub's /metrics
// endpoint, using the /state endpoint's JSON output for simplicity
// rather than parsing Prometheus text format by hand.
type HTTPMetricsProvider struct {
	Endpoint string // e.g. "http://metrics-stub:8080/state"
	Client   *http.Client
}

func NewHTTPMetricsProvider(endpoint string) *HTTPMetricsProvider {
	return &HTTPMetricsProvider{
		Endpoint: endpoint,
		Client:   &http.Client{},
	}
}

type stubStateResponse struct {
	KVCacheUsagePerc   float64 `json:"kv_cache_usage_perc"`
	NumRequestsWaiting int     `json:"num_requests_waiting"`
}

func (p *HTTPMetricsProvider) GetMetrics(ctx context.Context) (Metrics, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, p.Endpoint, nil)
	if err != nil {
		return Metrics{}, fmt.Errorf("building metrics request: %w", err)
	}

	resp, err := p.Client.Do(req)
	if err != nil {
		return Metrics{}, fmt.Errorf("calling metrics endpoint: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return Metrics{}, fmt.Errorf("metrics endpoint returned status %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return Metrics{}, fmt.Errorf("reading metrics response: %w", err)
	}

	return parsePrometheusMetrics(string(body))
}

func parsePrometheusMetrics(text string) (Metrics, error) {
	var m Metrics
	for _, line := range strings.Split(text, "\n") {
		fields := strings.Fields(line)
		if len(fields) != 2 {
			continue
		}
		switch fields[0] {
		case "vllm_kv_cache_usage_perc":
			v, err := strconv.ParseFloat(fields[1], 64)
			if err != nil {
				return Metrics{}, fmt.Errorf("parsing kv cache usage: %w", err)
			}
			m.KVCacheUsagePercent = int32(v * 100)
		case "vllm_num_requests_waiting":
			v, err := strconv.Atoi(fields[1])
			if err != nil {
				return Metrics{}, fmt.Errorf("parsing requests waiting: %w", err)
			}
			m.NumRequestsWaiting = int32(v)
		}
	}
	return m, nil
}
