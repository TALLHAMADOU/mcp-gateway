"""MCP Auto-Discovery: Generate tool schemas and registration commands."""

import json
import os
import yaml
from typing import Dict, Any, List


def generate_tool_schema(tool_name: str, description: str = "", input_schema: Dict = None) -> Dict[str, Any]:
    """Generate an MCP-compatible tool schema."""
    if input_schema is None:
        input_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    return {
        "name": tool_name,
        "description": description,
        "inputSchema": input_schema
    }


def get_all_tools() -> Dict[str, Dict[str, Any]]:
    """
    Collect all available tools from connectors, plugins, and built-in handlers.
    
    Returns:
        dict mapping tool_id to tool schema
    """
    tools = {}
    
    # 1. Built-in MCP tools (from mcp_server.py)
    builtin_tools = {
        "list_connectors": {
            "name": "list_connectors",
            "description": "List the connectors declared in servers.yaml",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        "fs_list": {
            "name": "fs_list",
            "description": "List a directory inside the gateway filesystem sandbox",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: '.')"
                    }
                },
                "required": []
            }
        },
        "fs_read": {
            "name": "fs_read",
            "description": "Read a UTF-8 text file inside the filesystem sandbox",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path"
                    }
                },
                "required": ["path"]
            }
        },
        "sql_query": {
            "name": "sql_query",
            "description": "Execute read-only SQL queries (SELECT only)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SELECT statement"
                    }
                },
                "required": ["sql"]
            }
        }
    }
    tools.update(builtin_tools)
    
    # 2. Dynamically loaded plugins
    try:
        from src.plugin_registry import list_plugins
        plugins = list_plugins()
        for plugin_id, plugin_info in plugins.items():
            tools[f"plugin_{plugin_id}"] = {
                "name": plugin_info.get("name", plugin_id),
                "description": plugin_info.get("description", "Plugin tool"),
                "inputSchema": plugin_info.get("inputSchema", {"type": "object", "properties": {}, "required": []})
            }
    except Exception as e:
        print(f"Warning: Failed to load plugins: {e}")
    
    # 3. Registered connectors
    try:
        config_path = os.path.join(os.getcwd(), 'servers.yaml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        for connector in config.get('connectors', []):
            connector_id = connector.get('id', 'unknown')
            connector_type = connector.get('type', 'unknown')
            tools[f"connector_{connector_id}"] = {
                "name": f"call_{connector_id}",
                "description": f"Call {connector_id} ({connector_type}) connector",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query or input for the connector"
                        }
                    },
                    "required": ["query"]
                }
            }
    except Exception as e:
        print(f"Warning: Failed to load connectors: {e}")
    
    return tools


def generate_mcp_registration_script(gateway_url: str = "http://localhost:8000", api_key: str = "sk_") -> str:
    """
    Generate shell commands to register the gateway with Claude, Cursor, etc.
    
    This creates a script that users can copy-paste to add the gateway to their
    MCP client configurations.
    
    Args:
        gateway_url: Gateway base URL (e.g., "http://localhost:8000")
        api_key: Gateway API key (masked in output)
    
    Returns:
        Shell script with MCP registration commands
    """
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "sk_..."
    
    script = f"""#!/bin/bash
# MCP Gateway Auto-Discovery Registration Script
# This script registers the MCP Gateway with your AI assistants

GATEWAY_URL="{gateway_url}"
API_KEY="{masked_key}"  # Update this with your actual key

echo "Registering MCP Gateway with your clients..."
echo "Gateway URL: $GATEWAY_URL"
echo "API Key: $API_KEY"
echo ""

# For Claude Desktop
echo "1. Claude Desktop:"
echo "   Edit ~/.config/Claude/claude_desktop_config.json and add:"
cat << 'JSON'
{{
  "mcpServers": {{
    "gateway": {{
      "url": "http://localhost:8000/mcp",
      "env": {{
        "MCP_GATEWAY_KEY": "your-api-key-here"
      }}
    }}
  }}
}}
JSON

echo ""
echo "2. Cursor IDE:"
echo "   Edit .cursor/mcp_config.json and add:"
cat << 'JSON'
{{
  "mcpServers": {{
    "gateway": {{
      "url": "http://localhost:8000/mcp",
      "env": {{
        "MCP_GATEWAY_KEY": "your-api-key-here"
      }}
    }}
  }}
}}
JSON

echo ""
echo "3. Using Copilot CLI:"
echo "   Run: copilot mcp add gateway --url http://localhost:8000/mcp --key your-api-key-here"
echo ""
echo "✅ Registration commands ready! Replace 'your-api-key-here' with your actual API key."
"""
    
    return script


def generate_tools_json() -> Dict[str, Any]:
    """Generate the tools list in MCP-compatible format."""
    tools = get_all_tools()
    
    return {
        "tools": list(tools.values()),
        "count": len(tools),
        "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
        "gateway_version": os.environ.get('VERSION', 'dev')
    }
