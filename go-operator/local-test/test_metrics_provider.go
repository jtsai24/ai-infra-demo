package main

import (
	"context"
	"fmt"

	"github.com/jtsai24/ai-infra-demo/operator/internal/controller"
)

func main() {
	provider := controller.NewHTTPMetricsProvider("http://localhost:8080/metrics")

	metrics, err := provider.GetMetrics(context.Background())
	if err != nil {
		fmt.Println("Error:", err)
		return
	}

	fmt.Printf("KV Cache Usage: %d%%\n", metrics.KVCacheUsagePercent)
	fmt.Printf("Requests Waiting: %d\n", metrics.NumRequestsWaiting)
}
