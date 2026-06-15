# MCP Gateway

> **Une seule porte d'entrée pour connecter tous vos outils à vos assistants IA.**
> Passerelle FastAPI qui expose filesystem, bases de données, GitHub, Docker, design, bureautique (Office / Google / Microsoft 365)… derrière **un endpoint MCP unique**, sécurisé par une clé API.

[![CI](https://github.com/TALLHAMADOU/mcp-gateway/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

---

## Table des matières

1. [Le problème](#le-problème)
2. [La solution](#la-solution)
3. [Avantages](#avantages)
4. [Architecture](#architecture)
5. [Connecteurs disponibles](#connecteurs-disponibles)
6. [Installation](#installation)
7. [Démarrage rapide](#démarrage-rapide)
8. [Brancher vos assistants IA (MCP)](#brancher-vos-assistants-ia-mcp)
9. [Génération bureautique (Office / Google / Microsoft 365)](#génération-bureautique-office--google--microsoft-365)
10. [Référence API REST](#référence-api-rest)
11. [Configuration & variables d'environnement](#configuration--variables-denvironnement)
12. [Sécurité](#sécurité)
13. [Tests](#tests)
14. [Ajouter un connecteur](#ajouter-un-connecteur)
15. [Roadmap](#roadmap)
16. [Licence](#licence)

---

## Le problème

Les assistants IA modernes (Claude Code, Codex, Gemini CLI, GitHub Copilot CLI) parlent le **MCP** (*Model Context Protocol*) pour accéder à des outils externes. Mais sans passerelle, chaque assistant doit :

- être configuré **individuellement** avec chaque outil (filesystem, DB, GitHub, Docker…) ;
- stocker **ses propres secrets** (tokens GitHub, DSN Postgres, clés API…) ;
- gérer son propre niveau de sécurité, ses propres garde-fous.

Résultat : configuration dupliquée, secrets éparpillés, surface d'attaque démultipliée.

## La solution

**MCP Gateway** centralise tout derrière **une seule URL** et **une seule clé API** :

```
Vos assistants IA  ──►  https://votre-gateway/mcp  ──►  tous vos outils
   (Claude, Codex,        (clé API unique)              (DB, GitHub, Docker,
    Gemini, Copilot)                                     Office, Drive, 365…)
```

Vous configurez vos secrets **une fois** sur la passerelle. Chaque assistant ne connaît qu'**une URL + un token**. Les garde-fous (SQL lecture seule, sandbox filesystem, suppression des en-têtes sensibles) sont appliqués **au même endroit, pour tout le monde**.

## Avantages

| Avantage | Détail |
|---|---|
| 🔌 **Un seul branchement** | Tous les assistants pointent vers `…/mcp`. Ajouter un outil = il apparaît partout, sans reconfigurer les clients. |
| 🔐 **Secrets centralisés** | Tokens et DSN vivent sur la passerelle (ou dans Vault), jamais dans la config de chaque assistant. |
| 🛡️ **Sécurité par défaut** | Auth obligatoire sur toutes les routes, SQL **lecture seule** (app + DB), sandbox filesystem confinée, en-têtes d'auth jamais relayés en amont. |
| 🧩 **Double interface** | Chaque connecteur est exposé à la fois en **MCP natif** (pour les IA) et en **REST `/v1/*`** (pour scripts/curl/CI). |
| 🏢 **Bureautique intégrée** | Génère DOCX/XLSX/PPTX en local, convertit en PDF (LibreOffice), pilote Google Workspace et Microsoft 365. |
| 🐳 **Prêt à conteneuriser** | Dockerfile + docker-compose (dev & prod), LibreOffice inclus dans l'image. |
| ✅ **Testé & en CI** | Suite `pytest` exécutée à chaque push (auth, sandbox, garde SQL, génération de documents). |

## Architecture

```
                         ┌──────────────────────────────────────────────┐
   Assistants IA         │                MCP GATEWAY (FastAPI)          │
 ┌──────────────┐        │                                              │
 │ Claude Code  │        │   /mcp  ── BearerAuthASGI ──► FastMCP server  │
 │ Codex        │ HTTP   │            (streamable HTTP)   │ in-process   │
 │ Gemini CLI   │ ─────► │                                ▼              │
 │ Copilot CLI  │ Bearer │   /v1/*  ── require_api_key ──► routers       │
 └──────────────┘        │                                │             │
                         │                                ▼             │
   Scripts / curl / CI   │            ┌──────────── handlers ─────────┐  │
 ┌──────────────┐  HTTP  │            │ fs · postgres · sqlite · github│  │
 │ REST /v1/*   │ ─────► │            │ notion · figma · docker · chrome│ │
 └──────────────┘        │            │ office · google_workspace      │  │
                         │            │ ms_graph · inkscape · gimp …   │  │
                         │            └────────────────────────────────┘  │
                         └──────────────────────────────────────────────┘
                                          │
        ┌──────────────┬─────────────┬────┴───────┬──────────────┬─────────────┐
        ▼              ▼             ▼            ▼              ▼             ▼
   Filesystem      Postgres/      GitHub/      Docker        LibreOffice   Google Drive /
   (sandbox)       SQLite (RO)    Notion/...   daemon        (PDF export)  Microsoft 365
```

**Idées clés :**

- **Deux façades, une logique.** Les outils MCP (`/mcp`) et les routes REST (`/v1/*`) appellent **les mêmes fonctions handler en in-process** — pas de saut HTTP interne, pas de double maintenance.
- **`servers.yaml` = source de vérité** de la liste des connecteurs.
- **Imports paresseux** des libs lourdes (python-docx, openpyxl, python-pptx) : une dépendance optionnelle manquante ne fait échouer que l'outil concerné, jamais toute la passerelle.
- **Auth en deux couches** : `require_api_key` (dépendance FastAPI) sur `/v1/*`, et un middleware ASGI `BearerAuthASGI` sur le sous-app MCP monté en `/mcp`.

### Arborescence

```
mcp-gateway/
├── src/
│   ├── main.py              # app FastAPI, montage /mcp, routers /v1/*, proxy
│   ├── auth.py              # require_api_key + API_KEY
│   ├── mcp_server.py        # serveur MCP natif (FastMCP) + outils
│   ├── sql_guard.py         # validation SELECT-only
│   └── handlers/            # un module par connecteur
│       ├── fs.py            # filesystem sandbox
│       ├── postgres.py      # Postgres lecture seule
│       ├── db.py            # SQLite lecture seule
│       ├── github.py notion.py figma.py docker_handler.py chrome_devtools.py
│       ├── office.py        # DOCX/XLSX/PPTX + conversion LibreOffice
│       ├── google_workspace.py   # Drive/Docs/Sheets/Slides
│       └── ms_graph.py      # OneDrive/Word/Excel/PPT (365)
├── servers.yaml            # déclaration des connecteurs
├── tests/                  # pytest (auth, sandbox, SQL guard, office)
├── Dockerfile · docker-compose.yml · docker-compose.prod.yml
└── requirements*.txt
```

## Connecteurs disponibles

| id | Catégorie | Ce qu'il fait | Pré-requis |
|---|---|---|---|
| `fs_local` | Système | Lecture fichiers/dossiers dans une sandbox | `FS_ROOT` |
| `postgres` | Base de données | Requêtes **SELECT only** (pool, timeout, limite lignes) | `POSTGRES_DSN` |
| `db_sqlite` | Base de données | Requêtes SQLite **SELECT only** (`mode=ro`) | fichier `.db` local |
| `github` | Dev | Proxy API GitHub (repos, issues, PR) | `GITHUB_TOKEN` |
| `notion` | Productivité | Proxy API Notion (pages, databases) | `NOTION_TOKEN` |
| `figma_local` | Design | Proxy API Figma (fichiers, nœuds) | `FIGMA_TOKEN` |
| `docker_local` | Infra | Inspection Docker (ps, images, inspect) | socket Docker |
| `chrome_devtools` | Web | Listing des cibles Chrome DevTools | Chrome `--remote-debugging-port=9222` |
| `office_local` | Bureautique | Génère DOCX/XLSX/PPTX + export PDF | LibreOffice (pour le PDF) |
| `google_workspace` | Bureautique | Drive / Docs / Sheets / Slides | `GOOGLE_ACCESS_TOKEN` |
| `ms_graph` | Bureautique | OneDrive / Word / Excel / PowerPoint (365) | `MS_GRAPH_TOKEN` |
| `inkscape_local` · `gimp_local` · `krita_local` · `synfig_local` · `blender_local` | Design/Création | Helpers locaux (logos, raster, vectoriel, animation, 3D) | logiciel installé |
| `git_remote` | Dev | Proxy générique vers un MCP distant (ex. Gitea) | service distant |

> Liste éditable dans [`servers.yaml`](./servers.yaml).

## Installation

### Pré-requis

- **Python 3.11+**
- (optionnel) **Docker** pour le déploiement conteneurisé
- (optionnel) **LibreOffice** (`soffice`) pour la conversion PDF du connecteur Office

### Option A — Local (Python)

```bash
git clone https://github.com/TALLHAMADOU/mcp-gateway.git
cd mcp-gateway

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # ou requirements-dev.txt pour les tests

cp .env.example .env                      # puis éditez vos secrets
export MCP_GATEWAY_KEY=sk_local_example   # clé d'auth (changez-la)

uvicorn src.main:app --reload --port 8080
```

### Option B — Docker

```bash
cp .env.example .env        # éditez vos secrets
docker compose up --build   # passerelle sur http://localhost:8080
```

L'image Docker embarque **LibreOffice** : la conversion PDF fonctionne sans installation supplémentaire.

## Démarrage rapide

```bash
export MCP_GATEWAY_KEY=sk_local_example
export GW=http://localhost:8080

# 1) Lister les connecteurs
curl -H "Authorization: Bearer $MCP_GATEWAY_KEY" $GW/v1/connectors

# 2) Lire un fichier (sandbox)
curl -H "Authorization: Bearer $MCP_GATEWAY_KEY" "$GW/v1/fs/read?path=README.md"

# 3) Générer une présentation PPTX (aucun compte requis)
curl -X POST $GW/v1/office/pptx \
  -H "Authorization: Bearer $MCP_GATEWAY_KEY" -H "Content-Type: application/json" \
  -d '{"filename":"demo","slides":[{"title":"MCP Gateway","bullets":["Un endpoint","Tous vos outils"]}]}'
# → {"ok": true, "path": ".../output/demo.pptx"}
```

> Sans en-tête `Authorization`, toutes les routes renvoient `401`. Avec une mauvaise clé : `403`.

## Brancher vos assistants IA (MCP)

La passerelle expose un **serveur MCP natif** sur `/mcp` (transport *streamable HTTP*), authentifié par `MCP_GATEWAY_KEY`. Le contrat est toujours le même : **URL `…/mcp` + en-tête `Authorization: Bearer <clé>`**.

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
# GitHub Copilot CLI
copilot mcp add --type http --url https://gw.example.com/mcp \
  --header "Authorization: Bearer $MCP_GATEWAY_KEY" mcp-gateway
```

### Outils MCP exposés

| Catégorie | Outils |
|---|---|
| **Registre** | `list_connectors` |
| **Filesystem** | `fs_list`, `fs_read` |
| **Bases de données** | `pg_query`, `sqlite_query` |
| **Dev** | `github_repo`, `github_issues`, `github_pulls`, `notion_page`, `notion_db_query`, `figma_file` |
| **Infra / Web** | `docker_ps`, `docker_images`, `docker_inspect`, `chrome_targets` |
| **Bureautique (local)** | `office_create_docx`, `office_create_xlsx`, `office_create_pptx`, `office_convert` |
| **Google Workspace** | `gdrive_files`, `gdoc_get`, `gdoc_create`, `gsheet_values`, `gslides_get` |
| **Microsoft 365** | `onedrive_root`, `onedrive_search`, `msexcel_worksheets`, `msexcel_range` |

> Le détail des flags peut varier selon la version de chaque CLI ; seul le couple **URL + Bearer** est invariant.

## Génération bureautique (Office / Google / Microsoft 365)

Trois approches complémentaires, selon où vivent vos données :

| Suite | Connecteur | Fonctionne où | Auth |
|---|---|---|---|
| **Local (Linux)** | `office_local` | Sur l'hôte, **sans compte** | aucune |
| **Cloud Google** | `google_workspace` | Sur vos Google Docs/Sheets/Slides | `GOOGLE_ACCESS_TOKEN` (OAuth2) |
| **Cloud Microsoft** | `ms_graph` | Sur OneDrive / Office 365 | `MS_GRAPH_TOKEN` (Azure AD) |

### Exemples (REST)

```bash
# DOCX
curl -X POST $GW/v1/office/docx -H "Authorization: Bearer $MCP_GATEWAY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"filename":"rapport","elements":[{"type":"heading","text":"Titre","level":1},{"type":"paragraph","text":"Contenu"}]}'

# XLSX
curl -X POST $GW/v1/office/xlsx -H "Authorization: Bearer $MCP_GATEWAY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"filename":"data","sheets":[{"name":"Ventes","rows":[["Mois","CA"],["Jan",1200]]}]}'

# Conversion en PDF (nécessite LibreOffice)
curl -X POST $GW/v1/office/convert -H "Authorization: Bearer $MCP_GATEWAY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"source_path":"output/rapport.docx","to":"pdf"}'
```

> 🎨 **Logos & designs** : utilisez les connecteurs **Inkscape** (vectoriel) et **GIMP** (raster) déjà présents. Il n'existe pas de MCP Photoshop/Adobe *headless* sous Linux — Microsoft Office bureau (Windows) n'est pas pilotable depuis une passerelle Linux, d'où le recours à **Microsoft Graph** pour le cloud 365.

### Obtenir les tokens cloud

- **Google** : mintez un `GOOGLE_ACCESS_TOKEN` via un *service account* ou l'[OAuth Playground](https://developers.google.com/oauthplayground) avec les scopes Drive/Docs/Sheets/Slides. La passerelle ne fait que le relayer.
- **Microsoft** : créez une *app registration* Azure AD (flux *client credentials* ou délégué) et récupérez un token Graph dans `MS_GRAPH_TOKEN`.

## Référence API REST

Toutes les routes exigent `Authorization: Bearer <MCP_GATEWAY_KEY>`.

| Méthode | Route | Description |
|---|---|---|
| `*` | `/mcp` | **Endpoint MCP natif** (assistants IA) |
| GET | `/v1/connectors` | Liste les connecteurs |
| POST | `/v1/admin/register` | Ajoute un connecteur (requiert aussi `ADMIN_KEY`) |
| `*` | `/v1/proxy/{connector_id}/{path}` | Proxy pour connecteurs `remote` |
| GET | `/v1/fs/list` · `/v1/fs/read` | Filesystem (sandbox `FS_ROOT`) |
| POST | `/v1/postgres/query` | SQL Postgres **SELECT only** |
| POST | `/v1/db/sqlite/query` | SQL SQLite **SELECT only** |
| GET | `/v1/github/repos/{owner}/{repo}` (`/issues`, `/pulls`) | Proxy GitHub |
| GET | `/v1/docker/ps` · `/images` · `/inspect/{id}` | Inspection Docker |
| GET | `/v1/chrome/targets` · `/target/{id}` | Chrome DevTools |
| POST | `/v1/office/docx` · `/xlsx` · `/pptx` · `/convert` | Génération bureautique |
| GET | `/v1/office/health` | État du connecteur Office (+ LibreOffice présent ?) |
| GET | `/v1/google-workspace/...` | Drive/Docs/Sheets/Slides |
| GET | `/v1/ms-graph/...` | OneDrive/Excel/Word/PPT |

Chaque handler expose aussi un `GET /health`.

## Configuration & variables d'environnement

`servers.yaml` déclare les connecteurs ; les secrets passent par l'environnement (ou Vault en prod). Voir [`.env.example`](./.env.example).

| Variable | Rôle |
|---|---|
| `MCP_GATEWAY_KEY` | **Clé API** d'authentification (obligatoire) |
| `ADMIN_KEY` | Protège `POST /v1/admin/register` si défini |
| `FS_ROOT` | Racine de la sandbox filesystem (défaut `.`) |
| `POSTGRES_DSN` / `DATABASE_URL` | Connexion Postgres |
| `PG_STATEMENT_TIMEOUT_MS` / `PG_MAX_ROWS` | Garde-fous Postgres |
| `GITHUB_TOKEN` · `NOTION_TOKEN` · `FIGMA_TOKEN` | Tokens des proxys API |
| `CHROME_DEBUG_HOST` | Endpoint CDP (défaut `http://localhost:9222`) |
| `OFFICE_OUTPUT_DIR` | Dossier de sortie (défaut `<FS_ROOT>/output`) |
| `GOOGLE_ACCESS_TOKEN` | Token Google Workspace |
| `MS_GRAPH_TOKEN` | Token Microsoft Graph |

### Production

Stack fournie : `docker-compose.prod.yml` + `scripts/deploy_prod.sh` + `infra/vault/`.

```bash
export VAULT_ADDR=...; export VAULT_TOKEN=...
./scripts/deploy_prod.sh
```

- Secrets dans **Vault** (KV v2, ex. `secret/mcp-gateway`), jamais committés.
- **Reverse-proxy TLS** (nginx/Traefik) en frontal.
- Rôle DB **lecture seule** dédié.

## Sécurité

| # | Point | Statut |
|---|---|---|
| 1 | Auth appliquée à **tous** les handlers (`dependencies=[Depends(require_api_key)]`) | ✅ |
| 2 | Sandbox filesystem `/v1/fs` (rejet chemins absolus + `..`, confiné à `FS_ROOT`) | ✅ |
| 3 | Le proxy ne relaie plus `authorization`/`host`/`content-length`/`connection` en amont, ni `content-encoding` en aval | ✅ |
| 4 | Garde SQL durcie (`sql_guard`) + transaction PG `READ ONLY` + SQLite `mode=ro` | ✅ |
| 5 | Dépendances épinglées (`requirements.txt`) | ✅ |
| 6 | Tests `pytest` exécutés en CI | ✅ |
| 7 | MCP `/mcp` protégé par middleware ASGI (`BearerAuthASGI`) | ✅ |
| 8 | `docker_inspect` expose la config (dont env) des conteneurs | ⚠️ par design — réserver aux environnements de confiance |

**Bonnes pratiques** : TLS en frontal, Vault pour les secrets, ne jamais exposer l'admin sans `ADMIN_KEY`, surveiller le pool DB.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Couvre : auth (401/403/200), confinement filesystem, garde SQL `SELECT`-only, états *non configurés* des connecteurs cloud, et génération réelle DOCX/XLSX/PPTX (vérification ZIP OOXML, sautée si les libs optionnelles sont absentes).

## Ajouter un connecteur

1. Déclarer l'entrée dans `servers.yaml` (`id`, `type`, `handler` ou `url` si `remote`).
2. Builtin : créer `src/handlers/<nom>.py` (un `APIRouter`) et le monter dans `src/main.py` avec `dependencies=_AUTH`.
3. (optionnel) Exposer un outil MCP dans `src/mcp_server.py` appelant la même fonction.
4. Ajouter un test + documenter l'endpoint. Redémarrer.

## Roadmap

- [x] Auth sur tous les handlers · sandbox filesystem · garde SQL read-only
- [x] Serveur MCP natif `/mcp` (streamable HTTP)
- [x] Suites bureautique (local / Google / Microsoft 365)
- [x] Tests + CI · dépendances épinglées
- [ ] Rate-limiting sur `/mcp` et `/v1/*`
- [ ] Refresh automatique des tokens OAuth (Google/MS)
- [ ] Auth avancée : OAuth2, mTLS, RBAC
- [ ] UI d'administration · proxy WebSocket CDP complet

## Contribution

Fork → branche `feature/*` → PR. Ajoutez des tests pour tout nouveau handler.

## Licence

[MIT](./LICENSE).
