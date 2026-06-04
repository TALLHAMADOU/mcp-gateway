Production deployment notes

Files included:
- docker-compose.prod.yml  : production docker-compose (uses .env.production)
- .env.production.example  : example env template (do NOT commit real secrets)
- scripts/deploy_prod.sh   : helper to fetch secrets from Vault and run docker-compose
- infra/vault/README.md    : Vault KV usage and examples

Steps (summary):
1) Provision Vault and store secrets under secret/mcp-gateway (KV v2)
2) On the deployment host, authenticate with Vault (VAULT_ADDR, VAULT_TOKEN)
3) Run ./scripts/deploy_prod.sh to fetch secrets and start services
4) Monitor logs: docker-compose -f docker-compose.prod.yml logs -f gateway

Operational recommendations:
- Use TLS termination (nginx/proxy) in front of the gateway.
- Use a process manager or orchestration (Kubernetes) for scaling and zero-downtime deploys.
- Integrate Prometheus metrics and set alerts for DB pool saturation.
