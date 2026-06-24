"""Dashboard endpoints and templates for admin UI."""

from fastapi import APIRouter, Request, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import os
import yaml
import logging
from datetime import datetime
import typing

dashboard_router = APIRouter()
audit_logger = logging.getLogger('mcp_audit')

# In-memory execution history (max 100 entries)
_EXECUTION_HISTORY = []
MAX_HISTORY = 100


def _add_to_history(connector_id: str, query: str, result: str, error: str = None, duration_ms: int = 0):
    """Add execution to in-memory history."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "connector_id": connector_id,
        "query": query,
        "result": result if not error else None,
        "error": error,
        "duration_ms": duration_ms
    }
    _EXECUTION_HISTORY.insert(0, entry)
    if len(_EXECUTION_HISTORY) > MAX_HISTORY:
        _EXECUTION_HISTORY.pop()


@dashboard_router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Render the dashboard home page."""
    # Load connectors from servers.yaml
    try:
        config_path = os.path.join(os.getcwd(), 'servers.yaml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        connectors = config.get('connectors', [])
    except Exception as e:
        connectors = []
        logging.error(f"Failed to load connectors: {e}")
    
    # Load plugins
    try:
        from src.plugin_registry import list_plugins
        plugins = list_plugins()
        plugin_count = len(plugins)
    except Exception:
        plugins = {}
        plugin_count = 0
    
    connector_count = len(connectors)
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MCP Gateway Dashboard</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
                color: #e0e0e0;
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 40px;
                padding-bottom: 20px;
                border-bottom: 1px solid #333;
            }}
            h1 {{ font-size: 28px; color: #fff; }}
            .nav-buttons {{
                display: flex;
                gap: 10px;
            }}
            button {{
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.3s;
            }}
            .btn-primary {{
                background: #4a9eff;
                color: white;
            }}
            .btn-primary:hover {{ background: #3a8eef; transform: translateY(-2px); }}
            .section {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid #333;
                border-radius: 8px;
                padding: 30px;
                margin-bottom: 30px;
                backdrop-filter: blur(10px);
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }}
            .card {{
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid #444;
                border-radius: 8px;
                padding: 20px;
                transition: all 0.3s;
            }}
            .card:hover {{ border-color: #4a9eff; background: rgba(74, 158, 255, 0.1); }}
            .card-title {{ font-weight: 600; font-size: 16px; margin-bottom: 10px; }}
            .status-ok {{ color: #4ade80; }}
            .status-error {{ color: #f87171; }}
            .stat {{
                font-size: 32px;
                font-weight: bold;
                color: #4a9eff;
                margin-top: 10px;
            }}
            .form-group {{
                margin-bottom: 15px;
            }}
            label {{
                display: block;
                margin-bottom: 5px;
                font-weight: 500;
            }}
            input, select, textarea {{
                width: 100%;
                padding: 10px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid #444;
                border-radius: 4px;
                color: #e0e0e0;
                font-family: inherit;
            }}
            textarea {{
                resize: vertical;
                min-height: 100px;
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 12px;
            }}
            .response {{
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid #444;
                border-radius: 4px;
                padding: 15px;
                margin-top: 15px;
                max-height: 400px;
                overflow-y: auto;
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 12px;
                white-space: pre-wrap;
                word-break: break-all;
            }}
            .tabs {{
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                border-bottom: 1px solid #333;
            }}
            .tab-btn {{
                padding: 10px 20px;
                background: none;
                border: none;
                border-bottom: 2px solid transparent;
                color: #999;
                cursor: pointer;
                font-weight: 500;
            }}
            .tab-btn.active {{
                border-color: #4a9eff;
                color: #4a9eff;
            }}
            .tab-content {{
                display: none;
            }}
            .tab-content.active {{
                display: block;
            }}
            .history-item {{
                background: rgba(0, 0, 0, 0.2);
                border-left: 3px solid #4a9eff;
                padding: 15px;
                margin-bottom: 10px;
                border-radius: 4px;
            }}
            .history-time {{
                font-size: 12px;
                color: #999;
                margin-bottom: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>🌉 MCP Gateway Dashboard</h1>
                    <p style="font-size: 14px; color: #999;">Manage connectors, test tools, and view history</p>
                </div>
                <div class="nav-buttons">
                    <button class="btn-primary" onclick="location.reload()">🔄 Refresh</button>
                </div>
            </header>

            <!-- Stats Section -->
            <div class="section">
                <h2 style="margin-bottom: 20px;">📊 Overview</h2>
                <div class="grid">
                    <div class="card">
                        <div class="card-title">Connected Connectors</div>
                        <div class="stat">{connector_count}</div>
                    </div>
                    <div class="card">
                        <div class="card-title">Available Plugins</div>
                        <div class="stat">{plugin_count}</div>
                    </div>
                    <div class="card">
                        <div class="card-title">API Status</div>
                        <div class="status-ok" style="margin-top: 10px;">✓ Running</div>
                    </div>
                </div>
            </div>

            <!-- Tabs -->
            <div class="section">
                <div class="tabs">
                    <button class="tab-btn active" onclick="switchTab('playground')">🎮 Playground</button>
                    <button class="tab-btn" onclick="switchTab('connectors')">🔗 Connectors</button>
                    <button class="tab-btn" onclick="switchTab('history')">📜 History</button>
                </div>

                <!-- Playground Tab -->
                <div id="playground" class="tab-content active">
                    <h3 style="margin-bottom: 20px;">Execute a Connector</h3>
                    <form onsubmit="executeConnector(event)">
                        <div class="form-group">
                            <label>Select Connector</label>
                            <select id="connector-select" required>
                                <option value="">-- Choose a connector --</option>
                                {chr(10).join(f'<option value="{c.get("id")}">{c.get("id")} ({c.get("type", "unknown")})</option>' for c in connectors)}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Query (JSON)</label>
                            <textarea id="query-input" placeholder='{{"example": "data"}}' required></textarea>
                        </div>
                        <button type="submit" class="btn-primary">▶ Execute</button>
                    </form>
                    <div id="response" style="display: none;">
                        <h4 style="margin-top: 20px; margin-bottom: 10px;">Response:</h4>
                        <div class="response" id="response-text"></div>
                    </div>
                </div>

                <!-- Connectors Tab -->
                <div id="connectors" class="tab-content">
                    <h3 style="margin-bottom: 20px;">Registered Connectors</h3>
                    <div class="grid">
                        {chr(10).join(f'''
                        <div class="card">
                            <div class="card-title">{c.get("id", "N/A")}</div>
                            <div style="font-size: 12px; color: #999; margin-bottom: 10px;">
                                Type: <strong>{c.get("type", "unknown")}</strong>
                            </div>
                            {f'<div style="font-size: 12px; color: #999;">URL: {c.get("url", "N/A")}</div>' if c.get("url") else ''}
                            <div class="status-ok" style="margin-top: 10px;">✓ Connected</div>
                        </div>
                        ''' for c in connectors)}
                    </div>
                </div>

                <!-- History Tab -->
                <div id="history" class="tab-content">
                    <h3 style="margin-bottom: 20px;">Execution History</h3>
                    <div id="history-list">
                        <p style="color: #999; text-align: center; padding: 40px;">No executions yet. Try the playground above!</p>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function switchTab(tabName) {{
                // Hide all tabs
                document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
                
                // Show selected tab
                document.getElementById(tabName).classList.add('active');
                event.target.classList.add('active');
            }}

            async function executeConnector(e) {{
                e.preventDefault();
                const connectorId = document.getElementById('connector-select').value;
                const query = document.getElementById('query-input').value;
                
                try {{
                    const response = await fetch(`/dashboard/execute`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ connector_id: connectorId, query: query }})
                    }});
                    
                    const data = await response.json();
                    document.getElementById('response').style.display = 'block';
                    document.getElementById('response-text').innerText = JSON.stringify(data, null, 2);
                }} catch (err) {{
                    document.getElementById('response').style.display = 'block';
                    document.getElementById('response-text').innerText = `Error: ${{err.message}}`;
                }}
            }}
        </script>
    </body>
    </html>
    """
    return html


@dashboard_router.post("/execute")
async def execute_connector(payload: dict):
    """Execute a connector query from the dashboard."""
    connector_id = payload.get("connector_id")
    query = payload.get("query")
    
    if not connector_id or not query:
        raise HTTPException(status_code=400, detail="Missing connector_id or query")
    
    try:
        # Load config
        config_path = os.path.join(os.getcwd(), 'servers.yaml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        connector = next((c for c in config.get('connectors', []) if c.get('id') == connector_id), None)
        if not connector:
            return {"error": f"Connector not found: {connector_id}"}
        
        # For now, just echo back the result (would call actual connector handlers here)
        return {
            "connector_id": connector_id,
            "query": query,
            "result": f"Mock response for {connector_id}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}
