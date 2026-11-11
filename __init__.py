"""postkitty: one post in, every platform out. Hermes Agent plugin entry point."""

from __future__ import annotations

from pathlib import Path

from . import cli, command, schemas, tools


def register(ctx) -> None:
    tools.configure(ctx)
    for name, schema in schemas.SCHEMAS.items():
        ctx.register_tool(name=name, toolset="postkitty", schema=schema, handler=tools.HANDLERS[name])
    ctx.register_skill("postkitty", Path(__file__).parent / "skills" / "postkitty" / "SKILL.md",
                       description="Turn one post into files for every social platform.")
    ctx.register_command("postkitty", handler=command.handle,
                         description="What postkitty does and example requests; add a platform name for its limits, "
                                     "or check <file> [target] to check a file.",
                         args_hint="[platform | check <file> [target]]")
    if hasattr(ctx, "register_cli_command"):  # absent on older Hermes
        ctx.register_cli_command(name="postkitty", help="Make and check social media files without the model",
                                 setup_fn=cli.setup, handler_fn=cli.run)
