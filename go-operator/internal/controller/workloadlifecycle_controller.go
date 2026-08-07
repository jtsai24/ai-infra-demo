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

	"github.com/go-logr/logr"
	appsv1 "k8s.io/api/apps/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/builder"
	"sigs.k8s.io/controller-runtime/pkg/client"
	logf "sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/predicate"

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

	metrics, err := r.observeMetrics(ctx, logger, &wl)
	if err != nil {
		logger.Error(err, "failed to fetch metrics")
		r.recordStatus(ctx, logger, &wl, statusUpdate{
			Reason:    "MetricsUnavailable",
			Available: metav1.ConditionFalse,
			Degraded:  metav1.ConditionTrue,
			Message:   err.Error(),
		})
		return ctrl.Result{RequeueAfter: 15 * time.Second}, nil
	}

	deploy, currentReplicas, err := r.observeDeployment(ctx, &wl)
	if err != nil {
		logger.Error(err, "unable to fetch target deployment", "deployment", wl.Spec.TargetDeployment)
		r.recordStatus(ctx, logger, &wl, statusUpdate{
			Reason:                      "TargetDeploymentNotFound",
			Available:                   metav1.ConditionFalse,
			Degraded:                    metav1.ConditionTrue,
			Message:                     err.Error(),
			ObservedKVCacheUsagePercent: &metrics.KVCacheUsagePercent,
		})
		return ctrl.Result{RequeueAfter: 15 * time.Second}, nil
	}

	desiredReplicas := computeDesiredReplicas(currentReplicas, metrics.KVCacheUsagePercent, wl.Spec)

	if err := r.makeAdjustmentIfNeeded(ctx, logger, &wl, &deploy, currentReplicas, desiredReplicas, metrics.KVCacheUsagePercent, wl.Spec.KVCacheThresholdPercent); err != nil {
		logger.Error(err, "failed to patch deployment replicas")
		return ctrl.Result{RequeueAfter: 15 * time.Second}, err
	}

	return ctrl.Result{RequeueAfter: 15 * time.Second}, nil
}

// statusUpdate describes one reconcile's status write. Pointer fields mean
// "leave this value as-is" when nil, since not every exit scenario has a
// fresh observation for every field (e.g. a metrics fetch failure has no new
// replica counts to report).
type statusUpdate struct {
	Reason    string
	Available metav1.ConditionStatus
	Degraded  metav1.ConditionStatus
	Message   string

	ObservedKVCacheUsagePercent *int32
	DesiredReplicas             *int32
	ScaledNow                   bool // true sets LastScaleTime to now
}

// recordStatus applies a statusUpdate to wl.Status in memory and persists it
// with a single Status().Update() call. Called at most once per Reconcile
// exit path.
func (r *WorkloadLifecycleReconciler) recordStatus(ctx context.Context, logger logr.Logger, wl *lifecyclev1alpha1.WorkloadLifecycle, u statusUpdate) {
	if u.ObservedKVCacheUsagePercent != nil {
		wl.Status.ObservedKVCacheUsagePercent = *u.ObservedKVCacheUsagePercent
	}
	if u.DesiredReplicas != nil {
		wl.Status.DesiredReplicas = *u.DesiredReplicas
	}
	if u.ScaledNow {
		now := metav1.Now()
		wl.Status.LastScaleTime = &now
	}

	wl.Status.LastTransitionReason = u.Reason
	meta.SetStatusCondition(&wl.Status.Conditions, metav1.Condition{
		Type:               "Available",
		Status:             u.Available,
		Reason:             u.Reason,
		Message:            u.Message,
		ObservedGeneration: wl.Generation,
	})
	meta.SetStatusCondition(&wl.Status.Conditions, metav1.Condition{
		Type:               "Degraded",
		Status:             u.Degraded,
		Reason:             u.Reason,
		Message:            u.Message,
		ObservedGeneration: wl.Generation,
	})

	if err := r.Status().Update(ctx, wl); err != nil {
		logger.Error(err, "failed to update WorkloadLifecycle status")
	}
}

// observeMetrics fetches current metrics from the workload's metrics endpoint.
func (r *WorkloadLifecycleReconciler) observeMetrics(ctx context.Context, logger logr.Logger, wl *lifecyclev1alpha1.WorkloadLifecycle) (Metrics, error) {
	provider := &HTTPMetricsProvider{
		Endpoint: wl.Spec.MetricsEndpoint,
		Client:   r.HTTPClient,
	}

	metrics, err := provider.GetMetrics(ctx)
	if err != nil {
		return Metrics{}, err
	}

	logger.Info("observed metrics",
		"kvCacheUsagePercent", metrics.KVCacheUsagePercent,
		"numRequestsWaiting", metrics.NumRequestsWaiting,
	)

	return metrics, nil
}

// observeDeployment fetches the target Deployment and its current replica count.
func (r *WorkloadLifecycleReconciler) observeDeployment(ctx context.Context, wl *lifecyclev1alpha1.WorkloadLifecycle) (appsv1.Deployment, int32, error) {
	var deploy appsv1.Deployment
	deployKey := client.ObjectKey{
		Namespace: wl.Namespace,
		Name:      wl.Spec.TargetDeployment,
	}
	if err := r.Get(ctx, deployKey, &deploy); err != nil {
		return appsv1.Deployment{}, 0, err
	}

	var currentReplicas int32 = 1
	if deploy.Spec.Replicas != nil {
		currentReplicas = *deploy.Spec.Replicas
	}

	return deploy, currentReplicas, nil
}

// makeAdjustmentIfNeeded logs the scaling decision, patches the Deployment if
// desiredReplicas differs from currentReplicas, and records the outcome
// (holding, scaled, or scale failed) to wl.Status.
func (r *WorkloadLifecycleReconciler) makeAdjustmentIfNeeded(ctx context.Context, logger logr.Logger, wl *lifecyclev1alpha1.WorkloadLifecycle, deploy *appsv1.Deployment, currentReplicas, desiredReplicas, kvCacheUsagePercent, thresholdPercent int32) error {
	if desiredReplicas == currentReplicas {
		logger.Info("no scaling action needed",
			"currentReplicas", currentReplicas,
			"kvCacheUsagePercent", kvCacheUsagePercent,
			"thresholdPercent", thresholdPercent,
		)
		r.recordStatus(ctx, logger, wl, statusUpdate{
			Reason:                      "Holding",
			Available:                   metav1.ConditionTrue,
			Degraded:                    metav1.ConditionFalse,
			ObservedKVCacheUsagePercent: &kvCacheUsagePercent,
			DesiredReplicas:             &desiredReplicas,
		})
		return nil
	}

	logger.Info("scaling decision",
		"currentReplicas", currentReplicas,
		"desiredReplicas", desiredReplicas,
		"kvCacheUsagePercent", kvCacheUsagePercent,
		"thresholdPercent", thresholdPercent,
	)

	reason := "ScaledUp"
	if desiredReplicas < currentReplicas {
		reason = "ScaledDown"
	}

	deploy.Spec.Replicas = &desiredReplicas
	if err := r.Update(ctx, deploy); err != nil {
		r.recordStatus(ctx, logger, wl, statusUpdate{
			Reason:                      "ScaleFailed",
			Available:                   metav1.ConditionTrue,
			Degraded:                    metav1.ConditionTrue,
			Message:                     err.Error(),
			ObservedKVCacheUsagePercent: &kvCacheUsagePercent,
			DesiredReplicas:             &desiredReplicas,
		})
		return err
	}

	r.recordStatus(ctx, logger, wl, statusUpdate{
		Reason:                      reason,
		Available:                   metav1.ConditionTrue,
		Degraded:                    metav1.ConditionFalse,
		ObservedKVCacheUsagePercent: &kvCacheUsagePercent,
		DesiredReplicas:             &desiredReplicas,
		ScaledNow:                   true,
	})
	return nil
}

// computeDesiredReplicas applies the hysteresis-band scaling rule: scale up
// when KV cache pressure crosses the high threshold, scale down when it
// drops below the low threshold, otherwise hold steady.
func computeDesiredReplicas(currentReplicas, kvCacheUsagePercent int32, spec lifecyclev1alpha1.WorkloadLifecycleSpec) int32 {
	switch {
	case kvCacheUsagePercent > spec.KVCacheThresholdPercent:
		desired := currentReplicas + 1
		if desired > spec.MaxReplicas {
			desired = spec.MaxReplicas
		}
		return desired
	case kvCacheUsagePercent < spec.KVCacheScaleDownThresholdPercent:
		desired := currentReplicas - 1
		if desired < spec.MinReplicas {
			desired = spec.MinReplicas
		}
		return desired
	default:
		return currentReplicas
	}
}

// SetupWithManager sets up the controller with the Manager.
func (r *WorkloadLifecycleReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&lifecyclev1alpha1.WorkloadLifecycle{}, builder.WithPredicates(predicate.GenerationChangedPredicate{})).
		Named("workloadlifecycle").
		Complete(r)
}
