"""postkitty: one post in, every platform out. Hermes Agent plugin entry point."""

from __future__ import annotations

from pathlib import Path

from . import tools


def register(ctx) -> None:
    tools.configure(ctx)
    for name, schema in tools.SCHEMAS.items():
        ctx.register_tool(name=name, toolset="postkitty", schema=schema, handler=tools.HANDLERS[name])
    ctx.register_skill("postkitty", Path(__file__).parent / "skills" / "postkitty" / "SKILL.md",
                       description="Turn one post into files for every social platform.")
    ctx.register_command("postkitty", handler=tools.targets_overview,
                         description="What postkitty does, example requests, and every platform target with its size and limits.",
                         args_hint="[platforms]")
