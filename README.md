MCP Gateway — Point d’entrée centralisé pour MCP (FastAPI)

Résumé
-------
MCP Gateway centralise et standardise l’accès à plusieurs MCP (connecteurs) pour vos CLI et agents IA. Objectif : partager configuration, secrets et outils (filesystem, git, GitHub, DB, Docker, Search, design APIs, Chrome DevTools, etc.) via un seul endpoint sécurisé.

Cas d’usage
----------
- Unifier la configuration MCP pour Claude Code, Codex, Gemini CLI et autres
- Exposer des handlers locaux (Inkscape, Blender, GIMP) et proxys API (GitHub, Notion, Figma)
- Fournir une façade sécurisée (API key / Vault) et protections (pooling, timeouts)

Fonctionnalités (MVP)
---------------------
- FastAPI gateway avec route /v1/connectors et /v1/proxy/{connector_id}
- Connecteurs builtin : filesystem, inkscape, gimp, krita, synfig, blender, figma, google-stitch, github, notion, chrome-devtools, docker, sqlite, postgres
- PostgreSQL read-only avec pooling, statement_timeout et limite de rows
- Notion / Figma / GitHub proxys (utilisent tokens via env)
- Docker SDK inspection endpoints, Chrome DevTools targets listing
- Admin minimal : POST /v1/admin/register pour ajouter dynamiquement un connector (modifie servers.yaml)

Connecteurs actuels (servers.yaml)
---------------------------------
1) fs_local
2) git_remote (remote)
3) inkscape_local
4) gimp_local
5) krita_local
6) synfig_local
7) blender_local
8) figma_local
9) google_stitch
10) github
11) db_sqlite
12) docker_local
13) chrome_devtools
14) notion
15) postgres

Installation — Développement (local)
-----------------------------------
1) Cloner : git clone <repo> && cd mcp-gateway
2) Créer venv et installer :
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
3) Lancer en local :
   export MCP_GATEWAY_KEY=sk_local_example
   ./scripts/dev.sh
4) Tests rapides :
   curl -H "Authorization: Bearer sk_local_example" http://localhost:8080/v1/connectors

Production (recommended)
------------------------
Stack fournie : docker-compose.prod.yml + script deploy_prod.sh + infra/vault instructions
- Stocker secrets dans Vault KV v2 (ex: secret/mcp-gateway)
- Sur la machine de déploiement :
  export VAULT_ADDR=...; export VAULT_TOKEN=...
  ./scripts/deploy_prod.sh
- Ne commitez jamais .env.production

Configuration & Secrets
-----------------------
- Configuration principale : servers.yaml (source of truth pour connectors)
- Secrets runtime : via Vault (preferred) ou .env.production (local/backups)
- Variables importantes :
  MCP_GATEWAY_KEY — clé API (Auth)
  GITHUB_TOKEN, NOTION_TOKEN, FIGMA_TOKEN — API tokens
  POSTGRES_DSN or DATABASE_URL — chaîne de connexion Postgres
  PG_MIN_CONN, PG_MAX_CONN, PG_STATEMENT_TIMEOUT_MS, PG_MAX_ROWS — pool + protections

Endpoints clés
--------------
- GET  /v1/connectors                       — lister connectors (auth)
- POST /v1/admin/register                   — ajouter connector (auth)
- GET  /v1/proxy/{connector_id}/{path}      — proxy pour connectors remote
- Builtin handlers: /v1/fs, /v1/github, /v1/postgres, /v1/db, /v1/docker, /v1/chrome, /v1/figma, etc.

Sécurité & bonnes pratiques
---------------------------
- TLS en frontal (nginx, Traefik) pour production
- Utiliser Vault pour gérer secrets et tokens
- Ne jamais exposer l’interface admin sans authentification forte
- Créer des rôles DB readonly pour le gateway
- Activer surveillance : Prometheus + alertes pour pool saturation

Exemples de configuration CLI
-----------------------------
- Variables d’environnement (recommandé) :
  export MCP_GATEWAY_URL="https://mcp-gateway.example.com"
  export MCP_GATEWAY_KEY="sk_prod..."

- Claude Code (exemple JSON config) :
  {
    "mcp": {"gateway": "https://mcp-gateway.example.com", "api_key": "sk_prod..."}
  }

- Codex / Gemini CLI (env) :
  export MCP_GATEWAY_URL=http://localhost:8080
  export MCP_GATEWAY_KEY=sk_local_example

Exemple d’appel GitHub via gateway :
  curl -H "Authorization: Bearer $MCP_GATEWAY_KEY" \
    http://localhost:8080/v1/github/repos/<owner>/<repo>

Comment ajouter un nouveau connector
-----------------------------------
1) Modifier servers.yaml et ajouter une entrée (id, type, handler, url si remote)
2) Pour handlers builtin : ajouter un module dans src/handlers et monter la route dans src/main.py
3) Redémarrer le service (ou reload si implémenté)
4) Écrire tests simples (curl) et documenter les endpoints

Observabilité & monitoring
--------------------------
- Recommander : exporter métriques Prometheus (request latencies, pool usage)
- Alerts : DB pool exhaustion, high latency, 5xx rate

Roadmap (prochaine phases)
--------------------------
- Auth avancée : OAuth2, mTLS, RBAC
- Vault Agent / Docker secrets injection
- Webhooks (GitHub) et in-process Git operations
- Chrome DevTools websocket proxy (full CDP)
- Search MCP (local rg/semantic)
- UI d’administration (liste/connectors/test)

Contribution
------------
- Fork, créer une branch feature/* puis PR
- Respecter tests unitaires et linters (préférences à définir)

Mots-clés pour GitHub (topics) — suggestions
-------------------------------------------
mcp-gateway, gateway, fastapi, ai-tooling, developer-tooling, devops, docker, postgres, github, notion, figma, chrome-devtools

Licence
-------
Choisir une licence (MIT recommandé) — inclure LICENSE dans le repo.

Contact
-------
Ouvrir une issue ou PR si vous souhaitez une intégration spécifique.

----

README généré automatiquement par l’agent. Adaptez la section "Production" selon vos règles d’exploitation.
