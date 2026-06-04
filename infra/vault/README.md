Vault integration for MCP Gateway (recommended production flow)

Overview
- Store all runtime secrets in Vault KV (v2). Do not commit secrets to Git.
- Use the vault CLI or a vault-agent sidecar to render a .env.production file consumed by docker-compose.

Recommended kv path: secret/data/mcp-gateway (KV v2)

Storing secrets (example):
# vault kv put secret/mcp-gateway \
#   MCP_GATEWAY_KEY=sk_prod_here \
#   POSTGRES_DSN='postgres://user:pass@host:5432/db' \
#   GITHUB_TOKEN=ghp_xxx \
#   NOTION_TOKEN=notion_xxx

Fetching secrets (example using vault CLI + jq):
1) Ensure VAULT_ADDR and VAULT_TOKEN are set in your shell.
2) vault kv get -format=json secret/mcp-gateway | \
   jq -r '.data.data | to_entries[] | "\(.key)=\(.value)"' > .env.production
3) Verify .env.production and keep it out of VCS (add to .gitignore).

Automated deploy script
- Use the provided scripts/deploy_prod.sh which wraps the above and then runs docker-compose -f docker-compose.prod.yml up -d --build

Security notes
- Use Vault policies to restrict who can read secret/mcp-gateway.
- Prefer dynamic DB credentials (database/creds) and short-lived tokens when possible.
- Consider using Vault Agent or Docker secrets for more secure injection into containers.
