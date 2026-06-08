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
| `office_local` | builtin | office | Génère DOCX/XLSX/PPTX + conversion PDF (LibreOffice headless) |
| `google_workspace` | builtin | google_workspace | Drive/Docs/Sheets/Slides, requiert `GOOGLE_ACCESS_TOKEN` |
| `ms_graph` | builtin | ms_graph | OneDrive/Word/Excel/PPT (365), requiert `MS_GRAPH_TOKEN` |

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
| `GOOGLE_ACCESS_TOKEN` | Token OAuth2 Google Workspace (Drive/Docs/Sheets/Slides) |
| `MS_GRAPH_TOKEN` | Token Microsoft Graph (OneDrive/Word/Excel/PPT 365) |
| `OFFICE_OUTPUT_DIR` | Dossier de sortie des fichiers générés (défaut `<FS_ROOT>/output`) |

## Endpoints

Toutes les routes ci-dessous exigent l'en-tête `Authorization: Bearer <MCP_GATEWAY_KEY>`.

| Méthode | Route | Description |
|---|---|---|
| * | `/mcp` | **Endpoint MCP natif** (streamable HTTP) — branchement des assistants IA |
| GET | `/v1/connectors` | Liste les connecteurs |
| POST | `/v1/admin/register` | Ajoute un connecteur (requiert aussi `ADMIN_KEY`) |
| * | `/v1/proxy/{connector_id}/{path}` | Proxy pour connecteurs `remote` |
| GET | `/v1/fs/list`, `/v1/fs/read` | Filesystem (sandbox `FS_ROOT`) |
| POST | `/v1/postgres/query`, `/v1/db/sqlite/query` | SQL SELECT-only (read-only) |
| GET | `/v1/docker/ps`, `/images`, `/inspect/{id}` | Inspection Docker |
| GET | `/v1/github/...`, `/v1/notion/...`, `/v1/figma/...` | Proxys API |
| GET | `/v1/chrome/targets` | Cibles Chrome DevTools |

## Brancher vos assistants IA (MCP — Option B)

Le gateway expose un **serveur MCP natif** sur `/mcp` (transport *streamable HTTP*), authentifié par `MCP_GATEWAY_KEY`. Les connecteurs sont exposés comme *tools* MCP appelés **in-process** :

- **Dev/infra** : `fs_read`, `fs_list`, `pg_query`, `sqlite_query`, `github_repo`, `github_issues`, `github_pulls`, `notion_page`, `notion_db_query`, `figma_file`, `docker_ps`, `docker_images`, `docker_inspect`, `chrome_targets`, `list_connectors`
- **Bureautique (local)** : `office_create_docx`, `office_create_xlsx`, `office_create_pptx`, `office_convert`
- **Google Workspace** : `gdrive_files`, `gdoc_get`, `gdoc_create`, `gsheet_values`, `gslides_get`
- **Microsoft 365 (Graph)** : `onedrive_root`, `onedrive_search`, `msexcel_worksheets`, `msexcel_range`

> ℹ️ La conversion/export PDF (`office_convert`) requiert **LibreOffice** installé sur l'hôte (`soffice`). Pour les **logos/designs**, utilise les connecteurs déjà présents **Inkscape** (vectoriel) et **GIMP** (raster) — il n'existe pas de MCP Photoshop/Adobe headless sous Linux.

```bash
# Claude Code
claude mcp add --transport http mcp-gateway https://gw.example.com/mcp \
  --header "Authorization: Bearer $MCP_GATEWAY_KEY"
```

```jsonc
// Gemini CLI — ~/.gemini/settings.json
{ "mcpServers": { "mcp-gateway": {
  "httpUrl": "https://gw.example.com/mcp",
  "headers": { "Authorization": "Bearer sk_prod..." }
}}}
```

```toml
# Codex CLI — ~/.codex/config.toml
[mcp_servers.mcp-gateway]
url = "https://gw.example.com/mcp"
headers = { Authorization = "Bearer sk_prod..." }
```

```bash
# GitHub Copilot CLI (serveur MCP HTTP, en-tête d'auth identique)
copilot mcp add --type http --url https://gw.example.com/mcp \
  --header "Authorization: Bearer $MCP_GATEWAY_KEY" mcp-gateway
```

> Le détail exact des flags/clés de config peut varier selon la version de chaque CLI ; le contrat reste : **URL `…/mcp` + en-tête `Authorization: Bearer`**.

## Sécurité & limitations connues

Ce dépôt était un MVP ; les trous critiques ont été corrigés. État actuel :

| # | Point | Statut |
|---|---|---|
| 1 | Auth appliquée à **tous** les handlers (`dependencies=[Depends(require_api_key)]`) | ✅ corrigé |
| 2 | Sandbox filesystem `/v1/fs` (rejet absolus + `..`, racine `FS_ROOT`) | ✅ corrigé |
| 3 | Le proxy ne retransmet plus `authorization`/`host`/`content-length`/`connection` | ✅ corrigé |
| 4 | `fs.py /read` : import `Response` manquant | ✅ corrigé |
| 5 | Garde SQL durcie (`sql_guard`) + transaction PG `READ ONLY` + SQLite `mode=ro` | ✅ corrigé |
| 6 | Dépendances épinglées (`requirements.txt`) | ✅ corrigé |
| 7 | Tests `pytest` + CI exécute la suite | ✅ corrigé |
| 8 | Docker `inspect` expose les env (secrets) des conteneurs | ⚠️ par design — restreindre via réseau/rôle |

> ⚠️ **Note Docker** : `docker_ps`/`docker_inspect` exposent la configuration des conteneurs (dont variables d'environnement). Réserver ce connecteur à des environnements de confiance.

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

- [x] Auth appliquée à tous les handlers (router-level dependency)
- [x] Confinement filesystem + correctif import `Response`
- [x] Garde SQL read-only (app + DB)
- [x] Tests unitaires + exécution en CI
- [x] Versions épinglées dans `requirements.txt`
- [x] Serveur MCP natif sur `/mcp` (streamable HTTP) — branchement des assistants
- [ ] Auth avancée : OAuth2, mTLS, RBAC
- [ ] Plugin loader réel (actuellement stub)
- [ ] Proxy WebSocket CDP complet (Chrome DevTools)
- [ ] UI d'administration

## Contribution

Fork → branche `feature/*` → PR. Ajouter des tests pour tout nouveau handler.

## Licence

[MIT](./LICENSE).
