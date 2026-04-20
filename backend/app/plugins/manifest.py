"""Plugin manifest and registry with dependency DAG topological sort."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PluginManifest:
    """Describes a plugin's capabilities, requirements, and constraints."""

    name: str
    version: str
    category: str  # e.g. "recon", "scanning", "web", "network", "cloud"
    is_intrusive: bool
    binary: str  # path or command name of the tool
    inputs: list[str] = field(default_factory=list)  # expected input types
    outputs: list[str] = field(default_factory=list)  # produced output types
    dependencies: list[str] = field(default_factory=list)  # plugin names this depends on
    rate_limit: int = 0  # max concurrent executions (0 = unlimited)
    timeout_seconds: int = 300  # default timeout
    safe_mode_allowed: bool = True  # can run in safe (non-intrusive) mode


class CyclicDependencyError(Exception):
    """Raised when the plugin dependency graph contains a cycle."""


class PluginNotFoundError(Exception):
    """Raised when a referenced plugin is not registered."""


class PluginRegistry:
    """Registry of all available plugins with topological sorting for execution order."""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginManifest] = {}

    def register(self, manifest: PluginManifest) -> None:
        """Register a plugin manifest."""
        self._plugins[manifest.name] = manifest

    def unregister(self, name: str) -> None:
        """Remove a plugin from the registry."""
        self._plugins.pop(name, None)

    def get(self, name: str) -> PluginManifest:
        """Get a plugin manifest by name."""
        if name not in self._plugins:
            raise PluginNotFoundError(f"Plugin '{name}' not found in registry")
        return self._plugins[name]

    def list_all(self) -> list[PluginManifest]:
        """Return all registered plugin manifests."""
        return list(self._plugins.values())

    def list_by_category(self, category: str) -> list[PluginManifest]:
        """Return plugins filtered by category."""
        return [p for p in self._plugins.values() if p.category == category]

    def list_safe_mode(self) -> list[PluginManifest]:
        """Return only plugins allowed in safe mode (non-intrusive)."""
        return [p for p in self._plugins.values() if p.safe_mode_allowed]

    def list_intrusive(self) -> list[PluginManifest]:
        """Return only intrusive plugins."""
        return [p for p in self._plugins.values() if p.is_intrusive]

    def topological_sort(self, plugin_names: list[str] | None = None) -> list[str]:
        """Return execution order via Kahn's algorithm (topological sort).

        Args:
            plugin_names: If provided, sort only these plugins (and validate
                their dependencies exist). If None, sort all registered plugins.

        Returns:
            List of plugin names in dependency-safe execution order.

        Raises:
            PluginNotFoundError: If a plugin or its dependency is not registered.
            CyclicDependencyError: If the dependency graph has a cycle.
        """
        if plugin_names is None:
            names = set(self._plugins.keys())
        else:
            names = set(plugin_names)

        # Validate all requested plugins exist
        for name in names:
            if name not in self._plugins:
                raise PluginNotFoundError(f"Plugin '{name}' not found in registry")

        # Build adjacency list and in-degree map for the subgraph
        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {name: 0 for name in names}

        for name in names:
            manifest = self._plugins[name]
            for dep in manifest.dependencies:
                if dep not in self._plugins:
                    raise PluginNotFoundError(
                        f"Plugin '{name}' depends on '{dep}' which is not registered"
                    )
                # Only include edge if dependency is in our subgraph
                if dep in names:
                    graph[dep].append(name)
                    in_degree[name] += 1

        # Kahn's algorithm
        queue: deque[str] = deque()
        for name in names:
            if in_degree[name] == 0:
                queue.append(name)

        sorted_order: list[str] = []
        while queue:
            node = queue.popleft()
            sorted_order.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(names):
            # Find cycle participants
            remaining = names - set(sorted_order)
            raise CyclicDependencyError(
                f"Cyclic dependency detected among plugins: {remaining}"
            )

        return sorted_order

    def get_execution_plan(
        self, plugin_names: list[str], safe_mode: bool = False
    ) -> list[PluginManifest]:
        """Get an ordered execution plan.

        Args:
            plugin_names: Plugins to include in the plan.
            safe_mode: If True, filter out intrusive plugins.

        Returns:
            Ordered list of PluginManifest objects.
        """
        ordered = self.topological_sort(plugin_names)
        plan = []
        for name in ordered:
            manifest = self._plugins[name]
            if safe_mode and not manifest.safe_mode_allowed:
                continue
            plan.append(manifest)
        return plan


# Global registry instance
registry = PluginRegistry()
