# Minikube: recommendation UI, API and Redis

This development demo deploys Streamlit, the recommendation API and a Redis
cache to the current Kubernetes namespace (default in the commands below). It
does not deploy PostgreSQL or enable the Graph/Batch admin job.

## Prerequisites

- Docker, Minikube and kubectl; enough resources for the API image and graph.
- The local `data/mgtab_user_trust_profiles_v2.csv`, an active graph registry
  at `artifacts/registry/active.json`, and all graph artifacts referenced by
  that registry. The active registry and generated graphs are ignored by Git,
  so a fresh checkout alone does not supply the demonstrated graph. Prepare or
  obtain these inputs separately before building; do not commit private data.
- The Dockerfile copies the local `artifacts/` directory into the API image.
  Verify that it contains only data appropriate for the image before building.

## Build and deploy (PowerShell)

Run from the repository root. The build may take several minutes.

```powershell
minikube start
kubectl config use-context minikube
minikube image build -t no-fraud-trust-service:redis-v1 .
minikube image build -f Dockerfile.ui -t no-fraud-pymk-ui:latest .
kubectl apply -f k8s/
kubectl rollout status deployment/redis --timeout=180s
kubectl rollout status deployment/trust-service --timeout=180s
kubectl rollout status deployment/pymk-ui --timeout=180s
kubectl get deployments,pods,services
```

Images are local to Minikube, not stored in Git or published to a registry.
Rebuild the images when their source or inputs change. Since both deployments
use `IfNotPresent`, rebuilding an existing tag does not restart running pods.
After rebuilding, restart the affected deployment, for example:

```powershell
kubectl rollout restart deployment/trust-service
kubectl rollout status deployment/trust-service --timeout=180s
```

## Verify

Run these in separate terminals and leave them open:

```powershell
kubectl port-forward service/trust-service 8000:8000
```

```powershell
kubectl port-forward service/pymk-ui 8501:8501
```

If port 8000 is occupied, use `8001:8000` and adjust the API URL below.
In another terminal:

```powershell
kubectl exec deployment/redis -- redis-cli ping
Invoke-RestMethod http://127.0.0.1:8000/health/ready
$body = '{"user_id":0,"top_k":5}'
1..2 | ForEach-Object {
  Invoke-RestMethod http://127.0.0.1:8000/v1/recommendations -Method Post -ContentType 'application/json' -Body $body |
    Select-Object user_id, graph_version, raw_cache_hit
}
```

Redis should return `PONG`, health should report `ready`, and the second
matching request should report `raw_cache_hit: True`. The first can already be
a hit; user 0 must exist in the active graph. Open http://127.0.0.1:8501 and
also verify the recommendation in the UI.

Redis is an ephemeral local cache with no persistent volume. The API image also
contains a snapshot of its artifacts; graph updates are not persistent across
pod replacement. This setup is for local validation, not production deployment.
The PostgreSQL-backed batch pipeline and persistent artifact storage require
separate configuration and verification.
