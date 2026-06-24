# 🎯 Suggestions d'Améliorations — MCP Gateway

<!-- BANDEAU HERO (Place ça tout en haut, sous le titre) -->
<p align="center">
  <img src="https://via.placeholder.com/800x400/0a0a0a/ffffff?text=Demo+GIF:+AI+Assistant+querying+Postgres+via+Gateway" alt="MCP Gateway Demo">
  <br>
  <em>🌉 Un seul endpoint. Tous vos assistants. Aucune configuration répétitive.</em>
</p>

---

## 🤔 Le Problème vs La Solution

| ❌ **Avant (Le cauchemar)** | ✅ **Après (Avec MCP Gateway)** |
| :--- | :--- |
| Configurer les tokens GitHub, DB, et Figma DANS chaque assistant (Claude, Cursor, Gemini). | Vos assistants ne voient **qu'une seule URL** (`http://gateway:8000`) et **une seule clé API**. |
| Multiplier les risques de fuite de secrets. | Gérez tous les accès depuis **un seul fichier `.env` centralisé**. |
| Code dupliqué pour chaque outil. | Les outils sont exposés à la fois en **MCP natif** (pour les IA) et en **REST** (pour vos scripts/CI). |

---

## 🚀 Démarrage en 30 secondes

Essayez-le **maintenant** :

```bash
# 1. Installez-le
git clone https://github.com/TALLHAMADOU/mcp-gateway.git && cd mcp-gateway
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 2. Lancez le serveur (avec une clé temporaire)
export MCP_GATEWAY_KEY="sk_demo123"
uvicorn src.main:app --reload --port 8080

# 3. Testez un outil (exemple: liste des connecteurs)
curl -H "Authorization: Bearer sk_demo123" http://localhost:8080/v1/connectors
```

---

## 📋 Les 4 Tickets Techniques à Implémenter

Voici les **4 squelettes de code / spécifications** exactes à implémenter. Copie chaque ticket dans ton assistant IA pour qu'il génère le code.

---

### 1️⃣ Système de Plugins Dynamiques (SDK pour Contributeurs)

**TICKET DEV : Plugin System**

Implémente un système de plugins dynamique dans le dossier `plugins/`.

**Objectif :** Permettre à n'importe quel utilisateur d'ajouter ses propres outils sans modifier le code de la gateway.

**Spécifications :**
1. Crée un décorateur `@tool` dans `src/plugin_registry.py`.
2. Au démarrage, scanne automatiquement tous les fichiers `.py` dans `plugins/` et charge les fonctions décorées.
3. Génère automatiquement le schéma JSON (OpenAPI / Pydantic) pour chaque outil à partir des type hints.
4. Ajoute les outils chargés à `/v1/connectors` et au serveur MCP natif.

**Exemple d'usage pour l'utilisateur final :**
```python
# plugins/mon_outil_perso.py
from mcp_gateway.plugin_registry import tool

@tool(name="meteo", description="Récupère la météo pour une ville donnée")
def get_weather(city: str, unit: str = "celsius") -> dict:
    """Récupère la météo actuelle.
    
    Args:
        city: Nom de la ville (ex: Paris)
        unit: Unité de température (celsius ou fahrenheit)
    
    Returns:
        dict avec temperature, condition, humidity
    """
    return {
        "temperature": 22,
        "unit": unit,
        "city": city,
        "condition": "Partiellement nuageux"
    }
```

**Endpoints à créer :**
- `POST /v1/plugins/register` — Enregistre un plugin (atomique, valide le `.py`).
- `GET /v1/plugins/list` — Liste les plugins chargés.
- `DELETE /v1/plugins/{plugin_id}` — Décharge un plugin.

---

### 2️⃣ Dashboard Admin + Playground

**TICKET DEV : Dashboard Admin (Interface Web)**

Crée une interface Web simple (FastAPI templates + Jinja2) sur la route `/dashboard`.

**Objectif :** Permettre aux non-techniciens (marketeurs, PMs) de tester les outils sans ouvrir le terminal.

**Spécifications :**
1. **Page d'accueil** : Liste tous les connecteurs activés avec leur statut (✅ vert / ❌ rouge).
   - Affiche aussi les tokens configurés (masqués, ex: `sk_****...xyz`).
2. **Playground** : Un formulaire pour :
   - Choisir un connecteur (dropdown).
   - Écrire une requête (exemple SQL, GitHub issue search, Figma node ID).
   - Bouton "Exécuter" → affiche la réponse brute en JSON + temps d'exécution.
   - Historique des 10 dernières requêtes (localStorage).
3. **Gestion des clés** : Formulaire pour mettre à jour les tokens d'API (ex: `GITHUB_TOKEN`) **sans redémarrer** le serveur.
   - Validation : tester la clé avant de la sauvegarder.
   - Audit : logger qui a changé quoi et quand.

**Routes :**
- `GET /dashboard` — Retourne l'HTML du dashboard.
- `POST /dashboard/execute` — Exécute une requête (body: `{connector_id, query}`).
- `POST /dashboard/tokens` — Met à jour un token.

---

### 3️⃣ Logs JSON + Prometheus + Health Checks

**TICKET DEV : Observabilité Complète**

Ajoute les logs JSON standardisés et les métriques Prometheus.

**Spécifications :**
1. **Logs JSON** : Permets de basculer au format JSON via `LOG_JSON=true`.
   - Chaque log inclut : `timestamp`, `level`, `message`, `actor` (API key masquée), `duration`, `status_code`.
   - Ingestion facile dans Datadog / Elastic / Grafana.
2. **Endpoint `/metrics`** (déjà partiellement implémenté) :
   - `mcp_requests_total` (compteur par endpoint et status).
   - `mcp_requests_duration_seconds` (histogramme, buckets: 0.01, 0.1, 1, 5).
   - `mcp_errors_total` (par type d'erreur).
   - `mcp_rate_limit_hits_total` (par API key).
   - `mcp_auth_failures_total`.
3. **Endpoint `/health`** (Kubernetes-ready) :
   - `GET /health` → `{"status": "ok", "redis": "ok", "postgres": "ok"}`
   - `GET /health/ready` → Même chose + ajoute `version`, `uptime_seconds`.

---

### 4️⃣ Auto-Discovery MCP (Claude Desktop / Cursor)

**TICKET DEV : MCP Auto-Discovery**

Implémente la découverte automatique des outils pour Claude Desktop, Cursor, et autres clients MCP.

**Objectif :** Les utilisateurs n'ont plus besoin de configurer manuellement chaque outil dans leur assistant.

**Spécifications :**
1. **Endpoint `/mcp/tools/list`** (route MCP standard) :
   - Retourne TOUS les connecteurs chargés (SQL, GitHub, Figma, Postgres, Docker...) avec :
     - `name` (ex: `postgres_query`)
     - `description` (ex: `Execute read-only SELECT against Postgres`)
     - `inputSchema` (Pydantic JSON Schema, généré automatiquement)
   - Format réponse :
     ```json
     {
       "tools": [
         {
           "name": "postgres_query",
           "description": "Execute read-only SELECT against Postgres",
           "inputSchema": {
             "type": "object",
             "properties": {
               "sql": {"type": "string", "description": "SELECT statement"},
               "params": {"type": "array", "items": {}}
             },
             "required": ["sql"]
           }
         },
         ...
       ]
     }
     ```

2. **Client MCP Registration** (pré-généré) :
   - Génère automatiquement les commandes `copilot mcp add`, `claude mcp add`, etc. à partir de la config.
   - Store dans un fichier `generated_mcp_commands.sh` pour que l'utilisateur copie-colle.

3. **Validation** :
   - Au chargement, valide que chaque tool possède `name`, `description`, et `inputSchema`.
   - Refuse les outils malformés.

---

## 🎯 Priorisation & Roadmap

| # | Ticket | Complexité | Impact | Priorité |
|---|--------|-----------|--------|----------|
| 1 | Plugin System | Moyen | Engagement ⬆️⬆️ | 🔴 **Haute** |
| 2 | Dashboard | Moyen | UX ⬆️⬆️ | 🟡 **Moyenne** |
| 3 | Observabilité | Faible | Ops ⬆️ | 🟡 **Moyenne** |
| 4 | Auto-Discovery | Faible | Adoption ⬆️ | 🟢 **Basse** |

---

## 💡 Conseils d'Implémentation

1. **Plugin System** : Commence par un système simple (import + validation). Laisse les plugins en RAM (pas de hot-reload au début).
2. **Dashboard** : Utilise `htmx.org` ou plain JavaScript pour les interactions sans rechargement.
3. **Observabilité** : Leverage la librarie `python-json-logger` pour les logs JSON.
4. **Auto-Discovery** : Réutilise le Pydantic introspection déjà en place.

---

## 📞 Questions ?

- Crée un issue GitHub avec le label `enhancement`.
- Ou ouvre une PR avec le code !

Bonne chance 🚀
