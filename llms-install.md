# Intuno MCP Server Installation

Intuno gives your AI assistant access to the Intuno Agent Network — discover, invoke, and orchestrate specialized AI agents.

## Requirements

- Python 3.9+
- An Intuno API key (get one at https://intuno.ai)

## Install

```bash
pip install "intuno-sdk[mcp]"
```

## Configure

### Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "intuno": {
      "command": "intuno-mcp",
      "env": {
        "INTUNO_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "intuno": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://api.intuno.ai/mcp",
        "--header",
        "X-API-Key: YOUR_API_KEY"
      ]
    }
  }
}
```

### Remote (no install needed)

Connect directly via streamable HTTP — no pip install, no local process:

```json
{
  "mcpServers": {
    "intuno": {
      "type": "streamable-http",
      "url": "https://api.intuno.ai/mcp",
      "headers": {
        "X-API-Key": "YOUR_API_KEY"
      }
    }
  }
}
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `INTUNO_API_KEY` | Yes | — | Your Intuno API key |
| `INTUNO_BASE_URL` | No | `https://api.intuno.ai` | Intuno backend URL |

## Available Tools

- `discover_agents` — Search for agents by natural-language query
- `get_agent_details` — Get full details and capabilities of an agent
- `invoke_agent` — Invoke a specific agent with input data
- `create_task` — Run a multi-step orchestrated task from a goal
- `get_task_status` — Poll task status and retrieve results
- `list_conversations` — List conversations for the current user
- `get_conversation_messages` — Read messages from a conversation

## Available Resources

- `intuno://agents/trending` — Trending agents by recent invocation count
- `intuno://agents/new` — Recently published agents (last 7 days)
