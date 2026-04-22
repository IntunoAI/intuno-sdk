"""Run the Intuno MCP server from Python instead of via the ``intuno-mcp`` CLI.

Useful when you want to embed the server in a larger process or override the
transport programmatically. Equivalent to running::

    INTUNO_API_KEY=wsk_... intuno-mcp --transport streamable-http --port 8080

Run:
    INTUNO_API_KEY=wsk_... python examples/mcp_server.py
"""

import os
import sys

from intuno_sdk.mcp_server import mcp


TRANSPORT = os.environ.get("INTUNO_MCP_TRANSPORT", "stdio")
PORT = int(os.environ.get("INTUNO_MCP_PORT", "8080"))


def main() -> None:
    if not os.environ.get("INTUNO_API_KEY"):
        print("Error: INTUNO_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    if TRANSPORT == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=TRANSPORT, port=PORT)


if __name__ == "__main__":
    main()
