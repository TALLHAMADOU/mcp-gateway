# MCP Gateway

> Point d'entrée centralisé pour MCP (Model Context Protocol) — FastAPI

MCP Gateway centralise et standardise l'accès à plusieurs connecteurs MCP pour vos CLI et agents IA (Claude Code, Codex, Gemini CLI…). Objectif : partager configuration, secrets et outils (filesystem, git, GitHub, DB, Docker, design APIs, Chrome DevTools…) derrière **un seul endpoint**.

> ⚠️ **Statut : MVP / non production-ready.** Voir [Sécurité & limitations connues](#sécurité--limitations-connues) avant toute exposition réseau.

---

## Cas d'usage

- Unifier la configuration MCP pour Claude Code, Codex, Gemini CLI et autres.
- Exposer des handlers locaux (Inkscape, Blender, GIMP, Krita, Synfig) et des proxys API (GitHub, Notion, Figma).
- Fournir une façade unique avec clé API et, en prod, secrets via Vault.

## Fonctionnalités (MVP)

- Gateway FastAPI : `/v1/connectors`, `/v1/proxy/{connector_id}/{path}`, `/v1/admin/register`.
- 14 connecteurs builtin (voir tableau).
- PostgreSQL **lecture seule** avec pooling, `statement_timeout` et limite de lignes.
- Proxys GitHub / Notion / Figma (tokens via variables d'environnement).
- Inspection Docker (SDK) et listing des cibles Chrome DevTools.
- Admin minimal : `POST /v1/admin/register` ajoute un connecteur dans `servers.yaml`.

## Connecteurs (`servers.yaml`)

| id | type | handler | Notes |
|---|---|---|---|
| `fs_local` | builtin_fs | — | Lecture fichiers (⚠️ voir limitations) |
| `git_remote` | remote | — | Proxy vers service gitea |
| `inkscape_local` | builtin | inkscape | Helper local |
| `gimp_local` | builtin | gimp | Helper local |
| `krita_local` | builtin | krita | Helper local |
| `synfig_local` | builtin | synfig | Helper local |
| `blender_local` | builtin | blender | Helper local |
| `figma_local` | builtin | figma | Requiert `FIGMA_TOKEN` |
| `google_stitch` | builtin | google_stitch | Placeholder (à clarifier) |
| `github` | builtin | github | Requiert `GITHUB_TOKEN` |
| `db_sqlite` | builtin | db | SQLite SELECT-only |
| `docker_local` | builtin | docker | Requiert accès au socket Docker |
| `chrome_devtools` | builtin | chrome_devtools | Requiert Chrome `--remote-debugging-port=9222` |
| `notion` | builtin | notion | Requiert `NOTION_TOKEN` |
| `postgres` | builtin | postgres | SELECT-only, requiert `POSTGRES_DSN`/`DATABASE_URL` |

## Développement (local)

```bash
git clone <repo> && cd mcp-gateway
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export MCP_GATEWAY_KEY=sk_local_example
./scripts/dev.sh                       # uvicorn --reload sur :8080

# test
curl -H "Authorization: Bearer sk_local_example" http://localhost:8080/v1/connectors
```

### Docker Compose

```bash
docker compose up --build
```

> ⚠️ **Bug connu** : dans `docker-compose.yml`, les services `gitea` et `browserless` exposent tous deux le port hôte `3000` → conflit au démarrage. Remappez l'un (ex. `browserless` sur `3001:3000`) avant de lancer.

## Production

Stack fournie : `docker-compose.prod.yml` + `scripts/deploy_prod.sh` + `infra/vault/`.

```bash
export VAULT_ADDR=...; export VAULT_TOKEN=...
./scripts/deploy_prod.sh
```

- Stocker les secrets dans Vault (KV v2, ex. `secret/mcp-gateway`).
- **Ne jamais committer `.env.production`** (déjà dans `.gitignore`).
- Mettre un reverse-proxy TLS (nginx / Traefik) en frontal.

## Configuration & secrets

- **Source de vérité des connecteurs** : `servers.yaml`.
- **Secrets runtime** : Vault (préféré) ou `.env.production`.

| Variable | Rôle |
|---|---|
| `MCP_GATEWAY_KEY` | Clé API d'authentification (défaut : `sk_local_example`) |
| `ADMIN_KEY` | Si défini, protège `POST /v1/admin/register` (Bearer) |
| `GITHUB_TOKEN` / `NOTION_TOKEN` / `FIGMA_TOKEN` | Tokens des proxys API |
| `POSTGRES_DSN` ou `DATABASE_URL` | Connexion Postgres |
| `PG_MIN_CONN` / `PG_MAX_CONN` / `PG_STATEMENT_TIMEOUT_MS` / `PG_MAX_ROWS` | Pool + garde-fous |
| `CHROME_DEBUG_HOST` | Endpoint CDP (défaut `http://localhost:9222`) |

## Endpoints

| Méthode | Route | Auth | Description |
|---|---|---|---|
| GET | `/v1/connectors` | ✅ clé API | Liste les connecteurs |
| POST | `/v1/admin/register` | ✅ clé API + `ADMIN_KEY` | Ajoute un connecteur à `servers.yaml` |
| * | `/v1/proxy/{connector_id}/{path}` | ✅ clé API | Proxy pour connecteurs `remote` |
| GET | `/v1/fs/list`, `/v1/fs/read` | ⚠️ **non authentifié** | Filesystem |
| POST | `/v1/postgres/query`, `/v1/db/sqlite/query` | ⚠️ **non authentifié** | SQL SELECT-only |
| GET | `/v1/docker/ps`, `/images`, `/inspect/{id}` | ⚠️ **non authentifié** | Inspection Docker |
| GET | `/v1/github/...`, `/v1/notion/...`, `/v1/figma/...` | ⚠️ **non authentifié** | Proxys API |
| GET | `/v1/chrome/targets`, `/v1/{handler}/health` | ⚠️ **non authentifié** | Divers |

## Sécurité & limitations connues

Ce dépôt est un **MVP**. Avant toute exposition réseau, traiter les points suivants :

1. **🔴 Handlers builtin non authentifiés.** `require_api_key` n'est appliqué qu'à `/v1/connectors`, `/v1/admin/register` et `/v1/proxy`. Tous les handlers (`/v1/fs`, `/v1/postgres`, `/v1/db`, `/v1/docker`, `/v1/github`…) sont **ouverts**. → appliquer la dépendance d'auth globalement (router-level `dependencies=[Depends(require_api_key)]`).
2. **🔴 Path traversal `/v1/fs`.** Aucune restriction de chemin : un chemin absolu ou `../` sort du répertoire de travail. → confiner sous une racine autorisée et rejeter `..` / chemins absolus.
3. **🔴 Le proxy retransmet l'`Authorization`** au connecteur amont (seul `host` est retiré). → filtrer `authorization` et headers sensibles.
4. **🟠 `fs.py` `/read`** référence `Response` sans l'importer → 500. → `from fastapi.responses import Response`.
5. **🟡 Garde SQL contournable** (`startswith("select")` : CTE `WITH`, requêtes empilées). `db.py` accepte un `db_path` arbitraire.
6. **🟡 `requirements.txt` non épinglé** → builds non reproductibles. → figer les versions.
7. **🟡 Aucun test** (la CI passe en « No tests to run »).
8. **🟡 Docker `inspect`** expose les variables d'env (secrets) des conteneurs.

### Bonnes pratiques de déploiement

- TLS en frontal, Vault pour les secrets, rôle DB en lecture seule dédié.
- Ne jamais exposer l'admin sans `ADMIN_KEY`.
- Surveiller la saturation du pool (Prometheus + alertes).

## Exemples CLI

```bash
export MCP_GATEWAY_URL="https://mcp-gateway.example.com"
export MCP_GATEWAY_KEY="sk_prod..."

# GitHub via gateway
curl -H "Authorization: Bearer $MCP_GATEWAY_KEY" \
  "$MCP_GATEWAY_URL/v1/github/repos/<owner>/<repo>"

# Postgres (SELECT only)
curl -X POST "$MCP_GATEWAY_URL/v1/postgres/query" \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT 1 AS ok"}'
```

Config Claude Code (exemple) :

```json
{ "mcp": { "gateway": "https://mcp-gateway.example.com", "api_key": "sk_prod..." } }
```

## Ajouter un connecteur

1. Ajouter une entrée dans `servers.yaml` (`id`, `type`, `handler` ou `url` si `remote`).
2. Pour un builtin : créer un module dans `src/handlers/` et monter la route dans `src/main.py`.
3. Redémarrer le service.
4. Ajouter un test et documenter l'endpoint.

## Roadmap

- [ ] Auth appliquée à tous les handlers (router-level dependency)
- [ ] Confinement filesystem + correctif import `Response`
- [ ] Auth avancée : OAuth2, mTLS, RBAC
- [ ] Tests unitaires + couverture CI
- [ ] Versions épinglées dans `requirements.txt`
- [ ] Plugin loader réel (actuellement stub)
- [ ] Proxy WebSocket CDP complet (Chrome DevTools)
- [ ] UI d'administration

## Contribution

Fork → branche `feature/*` → PR. Ajouter des tests pour tout nouveau handler.

## Licence

[MIT](./LICENSE).
