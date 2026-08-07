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

package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

// EDIT THIS FILE!  THIS IS SCAFFOLDING FOR YOU TO OWN!
// NOTE: json tags are required.  Any new fields you add must have json tags for the fields to be serialized.

type WorkloadLifecycleSpec struct {
	// TargetDeployment is the name of the Deployment this controller scales.
	// +kubebuilder:validation:Required
	// +kubebuilder:validation:MinLength=1
	TargetDeployment string `json:"targetDeployment"`

	// MetricsEndpoint is the URL of the metrics-stub /metrics endpoint.
	// +kubebuilder:validation:Required
	MetricsEndpoint string `json:"metricsEndpoint"`

	// KVCacheThresholdPercent is the KV cache usage percentage (0-100) above
	// which the controller scales up. Expressed as an integer, e.g. 80 for 80%.
	// +kubebuilder:validation:Required
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:validation:Maximum=100
	KVCacheThresholdPercent int32 `json:"kvCacheThresholdPercent"`

	// KVCacheScaleDownThresholdPercent: scale down when usage drops below this value.
	// Must be lower than KVCacheThresholdPercent to create a hysteresis band and avoid flapping.
	KVCacheScaleDownThresholdPercent int32 `json:"kvCacheScaleDownThresholdPercent"`

	// MinReplicas is the replica count when KV cache usage is below threshold.
	// +kubebuilder:validation:Required
	// +kubebuilder:validation:Minimum=1
	MinReplicas int32 `json:"minReplicas"`

	// MaxReplicas is the replica count when KV cache usage is above threshold.
	// +kubebuilder:validation:Required
	// +kubebuilder:validation:Minimum=1
	MaxReplicas int32 `json:"maxReplicas"`
}

// WorkloadLifecycleStatus defines the observed state of WorkloadLifecycle.
type WorkloadLifecycleStatus struct {
	// INSERT ADDITIONAL STATUS FIELD - define observed state of cluster
	// Important: Run "make" to regenerate code after modifying this file

	// For Kubernetes API conventions, see:
	// https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md#typical-status-properties

	// conditions represent the current state of the WorkloadLifecycle resource.
	// Each condition has a unique type and reflects the status of a specific aspect of the resource.
	//
	// Standard condition types include:
	// - "Available": the resource is fully functional
	// - "Progressing": the resource is being created or updated
	// - "Degraded": the resource failed to reach or maintain its desired state
	//
	// The status of each condition is one of True, False, or Unknown.
	// +listType=map
	// +listMapKey=type
	// +optional
	Conditions []metav1.Condition `json:"conditions,omitempty"`

	// ObservedKVCacheUsagePercent is the KV cache usage percentage observed
	// on the most recent reconcile.
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:validation:Maximum=100
	// +optional
	ObservedKVCacheUsagePercent int32 `json:"observedKVCacheUsagePercent,omitempty"`

	// DesiredReplicas is the replica count computed on the most recent reconcile.
	// +kubebuilder:validation:Minimum=1
	// +optional
	DesiredReplicas int32 `json:"desiredReplicas,omitempty"`

	// LastScaleTime is the last time the controller changed the target
	// Deployment's replica count.
	// +optional
	LastScaleTime *metav1.Time `json:"lastScaleTime,omitempty"`

	// LastTransitionReason describes the outcome of the most recent
	// scaling decision, e.g. "ScaledUp", "ScaledDown", "Holding".
	// +optional
	LastTransitionReason string `json:"lastTransitionReason,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status

// WorkloadLifecycle is the Schema for the workloadlifecycles API
type WorkloadLifecycle struct {
	metav1.TypeMeta `json:",inline"`

	// metadata is a standard object metadata
	// +optional
	metav1.ObjectMeta `json:"metadata,omitzero"`

	// spec defines the desired state of WorkloadLifecycle
	// +required
	Spec WorkloadLifecycleSpec `json:"spec"`

	// status defines the observed state of WorkloadLifecycle
	// +optional
	Status WorkloadLifecycleStatus `json:"status,omitzero"`
}

// +kubebuilder:object:root=true

// WorkloadLifecycleList contains a list of WorkloadLifecycle
type WorkloadLifecycleList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitzero"`
	Items           []WorkloadLifecycle `json:"items"`
}

func init() {
	SchemeBuilder.Register(func(s *runtime.Scheme) error {
		s.AddKnownTypes(SchemeGroupVersion, &WorkloadLifecycle{}, &WorkloadLifecycleList{})
		return nil
	})
}
