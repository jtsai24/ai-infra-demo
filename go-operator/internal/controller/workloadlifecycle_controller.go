/*
Copyright 2026.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package controller

import (
	"context"
	"net/http"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	logf "sigs.k8s.io/controller-runtime/pkg/log"

	lifecyclev1alpha1 "github.com/jtsai24/ai-infra-demo/operator/api/v1alpha1"
)

// WorkloadLifecycleReconciler reconciles a WorkloadLifecycle object
type WorkloadLifecycleReconciler struct {
	client.Client
	Scheme     *runtime.Scheme
	HTTPClient *http.Client // shared once, reused by every provider instance
}

// +kubebuilder:rbac:groups=lifecycle.ai-infra.demo,resources=workloadlifecycles,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=lifecycle.ai-infra.demo,resources=workloadlifecycles/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=lifecycle.ai-infra.demo,resources=workloadlifecycles/finalizers,verbs=update

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
// TODO(user): Modify the Reconcile function to compare the state specified by
// the WorkloadLifecycle object against the actual cluster state, and then
// perform operations to make the cluster state reflect the state specified by
// the user.
//
// For more details, check Reconcile and its Result here:
// - https://pkg.go.dev/sigs.k8s.io/controller-runtime@v0.24.1/pkg/reconcile
func (r *WorkloadLifecycleReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := logf.FromContext(ctx)
	var wl lifecyclev1alpha1.WorkloadLifecycle
	if err := r.Get(ctx, req.NamespacedName, &wl); err != nil {
		logger.Error(err, "unable to fetch WorkloadLifecycle")
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	provider := &HTTPMetricsProvider{
		Endpoint: wl.Spec.MetricsEndpoint,
		Client:   r.HTTPClient,
	}

	metrics, err := provider.GetMetrics(ctx)
	if err != nil {
		logger.Error(err, "failed to fetch metrics")
		return ctrl.Result{RequeueAfter: 15 * time.Second}, nil
	}

	logger.Info("observed metrics",
		"kvCacheUsagePercent", metrics.KVCacheUsagePercent,
		"numRequestsWaiting", metrics.NumRequestsWaiting,
	)

	var deploy appsv1.Deployment
	deployKey := client.ObjectKey{
		Namespace: wl.Namespace,
		Name:      wl.Spec.TargetDeployment,
	}
	if err := r.Get(ctx, deployKey, &deploy); err != nil {
		logger.Error(err, "unable to fetch target deployment", "deployment", wl.Spec.TargetDeployment)
		return ctrl.Result{RequeueAfter: 15 * time.Second}, nil
	}

	var currentReplicas int32 = 1
	if deploy.Spec.Replicas != nil {
		currentReplicas = *deploy.Spec.Replicas
	}

	desiredReplicas := currentReplicas
	if metrics.KVCacheUsagePercent > wl.Spec.KVCacheThresholdPercent {
		desiredReplicas = currentReplicas + 1
		if desiredReplicas > wl.Spec.MaxReplicas {
			desiredReplicas = wl.Spec.MaxReplicas
		}
	}

	if desiredReplicas != currentReplicas {
		logger.Info("scaling decision",
			"currentReplicas", currentReplicas,
			"desiredReplicas", desiredReplicas,
			"kvCacheUsagePercent", metrics.KVCacheUsagePercent,
			"thresholdPercent", wl.Spec.KVCacheThresholdPercent,
		)

		deploy.Spec.Replicas = &desiredReplicas
		if err := r.Update(ctx, &deploy); err != nil {
			logger.Error(err, "failed to patch deployment replicas")
			return ctrl.Result{RequeueAfter: 15 * time.Second}, err
		}
	} else {
		logger.Info("no scaling action needed",
			"currentReplicas", currentReplicas,
			"kvCacheUsagePercent", metrics.KVCacheUsagePercent,
			"thresholdPercent", wl.Spec.KVCacheThresholdPercent,
		)
	}

	return ctrl.Result{RequeueAfter: 15 * time.Second}, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *WorkloadLifecycleReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&lifecyclev1alpha1.WorkloadLifecycle{}).
		Named("workloadlifecycle").
		Complete(r)
}
