"""BaseAgent — the Claude tool-use loop every specialist inherits.

A specialist is a class with:
  - name, description, system_prompt
  - a list of Tool objects
  - a model from config.MODELS

Calling .run(task, context) drives a Claude loop until end_turn, executing
tools as it goes. Returns the final text output.

This is deliberately small. Don't add features here; add them in tools or
in subclass-specific run() overrides.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Callable
from dataclasses import dataclass, field

import anthropic

import config

log = logging.getLogger(__name__)


@dataclass
class Tool:
    """A tool available to an agent. The fn receives (state, **input)."""
    name: str
    description: str
    input_schema: dict
    fn: Callable[..., Any]

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class BaseAgent:
    name: str = "base"
    description: str = ""
    system_prompt: str = ""
    max_iterations: int = 12
    max_tokens: int = 4096

    def __init__(self, client: anthropic.Anthropic, state, tools: list[Tool] | None = None):
        self.client = client
        self.state = state
        self.tools = tools or []
        self.model = config.MODELS.get(self.name, "claude-haiku-4-5-20251001")

    # -- override in subclass to inject context into the user message --
    def build_input(self, task: str, context: dict | None = None) -> str:
        ctx = ""
        if context:
            ctx = "\n\nContext:\n" + json.dumps(context, indent=2, default=str)
        return f"{task}{ctx}"

    def run(self, task: str, context: dict | None = None) -> str:
        log.info("[%s] starting task: %s", self.name, task[:80])
        messages: list[dict] = [
            {"role": "user", "content": self.build_input(task, context)}
        ]

        for step in range(self.max_iterations):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self._full_system_prompt(),
                tools=[t.schema() for t in self.tools] if self.tools else [],
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                final = self._extract_text(response.content)
                self.state.log_run(self.name, "ok", summary=final[:500])
                return final

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        log.info("[%s] tool: %s", self.name, block.name)
                        try:
                            result = self._exec_tool(block.name, block.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": self._serialize(result),
                            })
                        except Exception as e:
                            log.exception("[%s] tool %s failed", self.name, block.name)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"ERROR: {e}",
                                "is_error": True,
                            })
                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason
            self.state.log_run(self.name, "error", error=f"stop_reason={response.stop_reason}")
            return self._extract_text(response.content)

        self.state.log_run(self.name, "error", error="max_iterations exceeded")
        return self._extract_text(response.content)

    # ---------- helpers ----------
    def _full_system_prompt(self) -> str:
        return (
            f"{self.system_prompt.strip()}\n\n"
            f"---\nFirm profile:\n{config.FIRM_PROFILE.strip()}"
        )

    def _exec_tool(self, name: str, args: dict) -> Any:
        for t in self.tools:
            if t.name == name:
                return t.fn(self.state, **args)
        raise ValueError(f"Unknown tool: {name}")

    @staticmethod
    def _extract_text(blocks) -> str:
        out = []
        for b in blocks:
            if getattr(b, "type", None) == "text":
                out.append(b.text)
        return "\n".join(out).strip()

    @staticmethod
    def _serialize(val: Any) -> str:
        if isinstance(val, (dict, list)):
            return json.dumps(val, default=str)
        return str(val)
