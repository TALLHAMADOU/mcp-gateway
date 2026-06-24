"""
Plugin Registry System

Allows users to dynamically load custom tools without modifying gateway code.
Each plugin is a Python file in plugins/ directory with @tool-decorated functions.
"""

import inspect
import importlib.util
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from functools import wraps
from pydantic import TypeAdapter, create_model
from pydantic.json_schema import GenerateJsonSchema

logger = logging.getLogger(__name__)

# Global registry: plugin_id -> ToolDefinition
_PLUGIN_REGISTRY: Dict[str, "ToolDefinition"] = {}


class ToolDefinition:
    """Metadata for a tool loaded via @tool decorator."""
    
    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        module_path: str
    ):
        self.name = name
        self.description = description
        self.func = func
        self.module_path = module_path
        self.plugin_id = f"{Path(module_path).stem}_{name}"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict with schema."""
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "description": self.description,
            "module": Path(self.module_path).stem,
            "inputSchema": self.get_input_schema(),
            "status": "ok"
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Generate OpenAPI/JSON Schema from function signature."""
        sig = inspect.signature(self.func)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
                
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
            
            # Convert Python types to JSON Schema
            schema_type = _python_type_to_schema(param_type)
            
            prop = {"type": schema_type}
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
            
            # Add docstring hint if available
            if self.func.__doc__:
                docstring_lines = self.func.__doc__.split("\n")
                for line in docstring_lines:
                    if param_name in line and ":" in line:
                        prop["description"] = line.split(":", 1)[1].strip()
                        break
            
            properties[param_name] = prop
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    async def call(self, **kwargs) -> Any:
        """Execute the tool with the given arguments."""
        if inspect.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        else:
            return self.func(**kwargs)


def tool(name: str, description: str):
    """
    Decorator to register a function as a tool.
    
    Usage:
        @tool(name="weather", description="Get weather for a city")
        def get_weather(city: str) -> dict:
            return {"temp": 22, "city": city}
    """
    def decorator(func: Callable) -> Callable:
        # Store metadata on the function
        func._tool_name = name
        func._tool_description = description
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper._tool_name = name
        wrapper._tool_description = description
        wrapper._is_tool = True
        return wrapper
    
    return decorator


def load_plugins(plugins_dir: Optional[str] = None) -> Dict[str, ToolDefinition]:
    """
    Scan plugins/ directory and load all @tool-decorated functions.
    
    Args:
        plugins_dir: Path to plugins directory (default: ./plugins)
    
    Returns:
        Dictionary of plugin_id -> ToolDefinition
    """
    if plugins_dir is None:
        plugins_dir = Path(__file__).parent.parent / "plugins"
    else:
        plugins_dir = Path(plugins_dir)
    
    if not plugins_dir.exists():
        logger.info(f"Plugins directory does not exist: {plugins_dir}")
        return {}
    
    logger.info(f"Loading plugins from {plugins_dir}")
    
    for py_file in sorted(plugins_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        
        try:
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Scan for @tool-decorated functions
                for name, obj in inspect.getmembers(module):
                    if callable(obj) and hasattr(obj, "_is_tool"):
                        tool_name = obj._tool_name
                        tool_desc = obj._tool_description
                        tool_def = ToolDefinition(
                            name=tool_name,
                            description=tool_desc,
                            func=obj,
                            module_path=str(py_file)
                        )
                        _PLUGIN_REGISTRY[tool_def.plugin_id] = tool_def
                        logger.info(f"Loaded plugin: {tool_def.plugin_id}")
        
        except Exception as e:
            logger.error(f"Failed to load plugin {py_file}: {e}", exc_info=True)
    
    return _PLUGIN_REGISTRY


def get_plugin(plugin_id: str) -> Optional[ToolDefinition]:
    """Retrieve a loaded plugin by ID."""
    return _PLUGIN_REGISTRY.get(plugin_id)


def list_plugins() -> Dict[str, Dict[str, Any]]:
    """List all loaded plugins with metadata."""
    return {
        plugin_id: tool_def.to_dict()
        for plugin_id, tool_def in _PLUGIN_REGISTRY.items()
    }


def unload_plugin(plugin_id: str) -> bool:
    """Remove a plugin from registry."""
    if plugin_id in _PLUGIN_REGISTRY:
        del _PLUGIN_REGISTRY[plugin_id]
        logger.info(f"Unloaded plugin: {plugin_id}")
        return True
    return False


def _python_type_to_schema(python_type: Any) -> str:
    """Convert Python type to JSON Schema type string."""
    if python_type == str or python_type == "str":
        return "string"
    elif python_type == int or python_type == "int":
        return "integer"
    elif python_type == float or python_type == "number":
        return "number"
    elif python_type == bool or python_type == "bool":
        return "boolean"
    elif python_type == list or python_type == "list":
        return "array"
    elif python_type == dict or python_type == "dict":
        return "object"
    else:
        return "string"  # fallback
