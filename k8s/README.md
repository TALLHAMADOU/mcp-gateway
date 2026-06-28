# Kubernetes manifests

Minimal, hardened manifests to run the MCP Gateway on Kubernetes.

## Files
- `deployment.yaml` — 2 replicas, non-root, read-only rootfs, dropped caps,
  liveness (`/health/live`) and readiness (`/health/ready`, returns 503 when a
  dependency is down) probes, writable `/data` + `/tmp` via `emptyDir`.
- `service.yaml` — `ClusterIP` exposing port 80 → container `8080`.
- `secret.example.yaml` — template for the env secret (do **not** commit real keys).

## Deploy
```bash
# 1. Build & push your image, then set it in deployment.yaml (image:)
docker build -t <registry>/mcp-gateway:<tag> .
docker push <registry>/mcp-gateway:<tag>

# 2. Create the secret (out-of-band, not from the example file)
kubectl create secret generic mcp-gateway-secrets \
  --from-literal=MCP_GATEWAY_KEY=sk_... \
  --from-literal=POSTGRES_DSN=postgres://...

# 3. Apply
kubectl apply -f k8s/service.yaml -f k8s/deployment.yaml
```

## Notes
- `/data` is an `emptyDir` (ephemeral). For a durable audit trail, replace it
  with a `PersistentVolumeClaim`.
- Add an `Ingress` (or `Service type: LoadBalancer`) to expose `/mcp` and `/v1/*`
  externally; terminate TLS at the ingress.
- Set `REDIS_URL` in the secret to switch rate-limiting to the distributed
  (Redis) backend across replicas.
