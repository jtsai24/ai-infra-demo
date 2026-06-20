resource "helm_release" "prometheus" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "prometheus"
  namespace  = "default"

  values = [file("helm/prometheus-values.yaml")]

  timeout = 300

  depends_on = [kubernetes_deployment.vllm]
}

resource "helm_release" "loki" {
  name       = "loki"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki"
  namespace  = "default"

  values = [file("helm/loki-values.yaml")]

  set {
    name  = "loki.useTestSchema"
    value = "true"
  }

  timeout = 300

  depends_on = [kubernetes_deployment.vllm]
}

resource "helm_release" "promtail" {
  name       = "promtail"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "promtail"
  namespace  = "default"

  values = [file("helm/promtail-values.yaml")]

  timeout = 300

  depends_on = [helm_release.loki]
}

resource "helm_release" "grafana" {
  name       = "grafana"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "grafana"
  namespace  = "default"

  values = [file("helm/grafana-values.yaml")]

  timeout = 300

  depends_on = [helm_release.prometheus, helm_release.loki]
}