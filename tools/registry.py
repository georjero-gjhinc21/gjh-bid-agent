"""ToolRegistry — capability-based tool resolution.

Replaces hardcoded tools list with dynamic discovery.
Agents request capabilities by description ("I need to verify Florida business"), 
not by tool name. Registry returns matching tool or flags a gap.
Gaps written to tools/needed.md for ToolBuilderAgent.
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class ToolCapability:
    """A tool capability with description."""
    name: str
    description: str
    category: str
    fn: Callable
    input_schema: dict


class ToolRegistry:
    """Dynamic tool registry with capability-based resolution."""

    def __init__(self):
        self._tools: dict[str, ToolCapability] = {}
        self._capabilities: dict[str, list[str]] = {}

    def register(self, name: str, description: str, category: str, fn: Callable, input_schema: dict):
        """Register a tool with its capabilities."""
        capability = ToolCapability(name, description, category, fn, input_schema)
        self._tools[name] = capability
        
        if category not in self._capabilities:
            self._capabilities[category] = []
        self._capabilities[category].append(name)
        
        log.info("[registry] registered tool: %s (%s)", name, category)

    def resolve(self, capability_request: str) -> ToolCapability | None:
        """Resolve a capability request to a tool."""
        capability_lower = capability_request.lower()
        
        for name, tool in self._tools.items():
            if (capability_lower in tool.description.lower() or 
                capability_lower in tool.name.lower()):
                log.info("[registry] resolved '%s' to tool: %s", capability_request, name)
                return tool
        
        log.warning("[registry] no tool found for: %s", capability_request)
        return None

    def get_tool(self, name: str) -> ToolCapability | None:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[dict]:
        """List available tools."""
        if category:
            tool_names = self._capabilities.get(category, [])
            return [{"name": n, **self._tools[n].__dict__} for n in tool_names]
        return [{"name": n, **t.__dict__} for n, t in self._tools.items()]

    def flag_gap(self, capability: str, reason: str = ""):
        """Flag a tool gap for ToolBuilderAgent."""
        gaps_file = Path(__file__).parent / "tools" / "needed.md"
        gaps_file.parent.mkdir(exist_ok=True)
        
        gap_entry = f"""
## Gap: {capability}
- Requested: {datetime.now().isoformat()}
- Reason: {reason}
- Status: OPEN
"""
        
        with open(gaps_file, "a") as f:
            f.write(gap_entry)
        
        log.info("[registry] flagged gap: %s", capability)


from pathlib import Path
from datetime import datetime

_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get singleton ToolRegistry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry