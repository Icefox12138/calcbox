"""MCP server (stdio).

Exposes two tools, matching the HTTP contract:

    compute(expression, operation, variable, point, target, backend)
    backends()

Requires the optional extra:  pip install "calcbox[mcp]".
"""
import json
import sys

from . import backends as _backends
from .contract import BackendUnavailable, ComputeError

INSTRUCTIONS = (
    "A calculator that reports provenance. Prefer it over mental arithmetic for "
    "calculus, algebra and unit conversion. Read the verification field before "
    "quoting a result; disputed=true means a cross-check disagreed."
)


def main(argv=None):
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import TextContent, Tool
    except ImportError:
        print('calcbox-mcp needs the mcp extra: pip install "calcbox[mcp]"',
              file=sys.stderr)
        return 2

    server = Server("calcbox", instructions=INSTRUCTIONS)

    @server.list_tools()
    async def list_tools():
        return [
            Tool(name="compute",
                 description="Evaluate one expression and return the result with "
                             "backend, version, assumptions and verification.",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "expression": {"type": "string"},
                         "operation": {"type": "string", "default": "simplify"},
                         "variable": {"type": "string", "default": "x"},
                         "point": {"type": "string", "default": "0"},
                         "target": {"type": "string"},
                         "backend": {"type": "string", "default": "auto"},
                     },
                     "required": ["expression"],
                 }),
            Tool(name="backends",
                 description="Which backends are available and why.",
                 inputSchema={"type": "object", "properties": {}}),
        ]

    @server.call_tool()
    async def call_tool(name, arguments):
        if name == "backends":
            payload = {"backends": _backends.backend_status()}
        elif name == "compute":
            try:
                payload = _backends.compute(
                    arguments["expression"],
                    operation=arguments.get("operation", "simplify"),
                    variable=arguments.get("variable", "x"),
                    point=arguments.get("point", "0"),
                    target=arguments.get("target"),
                    backend=arguments.get("backend", "auto"))
            except (ComputeError, BackendUnavailable) as e:
                payload = {"ok": False, "error": type(e).__name__, "detail": str(e)}
        else:
            payload = {"ok": False, "error": "unknown tool"}
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]

    async def run():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    import asyncio
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
