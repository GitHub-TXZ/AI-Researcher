from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from pydantic import BaseModel


class ToolParam(BaseModel):
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True


class Tool(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def run(self, params: dict[str, Any]) -> str: ...

    def schema(self) -> list[ToolParam]:
        return [ToolParam(name="input", description="primary argument")]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def add(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def describe(self) -> str:
        if not self._tools:
            return "(no tools)"
        return "\n".join(f"- {t.name}: {t.description}" for t in self._tools.values())

    def run(self, name: str, params: dict[str, Any]) -> str:
        tool = self.get(name)
        if not tool:
            return f"Unknown tool: {name}"
        return tool.run(params)

    def catalog(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]


EventFn = Callable[[dict[str, Any]], None]
