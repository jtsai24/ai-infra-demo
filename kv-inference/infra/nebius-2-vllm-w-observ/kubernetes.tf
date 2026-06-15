resource "kubernetes_secret" "hf_token" {
  metadata {
    name      = "hf-token"
    namespace = "default"
  }

  data = {
    token = var.hf_token
  }

  depends_on = [nebius_mk8s_v1_node_group.h100]
}

resource "kubernetes_deployment" "vllm" {
  metadata {
    name      = "vllm"
    namespace = "default"
    labels = {
      app = "vllm"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "vllm"
      }
    }

    template {
      metadata {
        labels = {
          app = "vllm"
        }
      }

      spec {
        toleration {
          key      = "nvidia.com/gpu"
          operator = "Exists"
          effect   = "NoSchedule"
        }

        container {
          name  = "vllm"
          image = "vllm/vllm-openai:latest"

          args = [
            "--model", var.vllm_model,
            "--host", "0.0.0.0",
            "--port", "8000",
            "--gpu-memory-utilization", "0.90",
          ]

          port {
            name           = "http"
            container_port = 8000
            protocol       = "TCP"
          }

          env {
            name = "HUGGING_FACE_HUB_TOKEN"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.hf_token.metadata[0].name
                key  = "token"
              }
            }
          }

          resources {
            limits = {
              "nvidia.com/gpu" = "1"
              "memory"         = "180Gi"
              "cpu"            = "14"
            }
            requests = {
              "nvidia.com/gpu" = "1"
              "memory"         = "160Gi"
              "cpu"            = "12"
            }
          }

          startup_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            failure_threshold = 60
            period_seconds    = 10
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 10
            period_seconds        = 10
            failure_threshold     = 3
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 30
            period_seconds        = 30
            failure_threshold     = 3
          }

          volume_mount {
            name       = "shm"
            mount_path = "/dev/shm"
          }
        }

        volume {
          name = "shm"
          empty_dir {
            medium     = "Memory"
            size_limit = "16Gi"
          }
        }
      }
    }
  }

  timeouts {
    create = "15m"
    update = "15m"
  }

  depends_on = [
    nebius_mk8s_v1_node_group.h100,
    kubernetes_secret.hf_token,
  ]
}

resource "kubernetes_service" "vllm" {
  metadata {
    name      = "vllm"
    namespace = "default"
  }

  spec {
    selector = {
      app = "vllm"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = 8000
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }

  depends_on = [kubernetes_deployment.vllm]
}