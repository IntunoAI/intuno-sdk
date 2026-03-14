# Intuno Python SDK

The official Python SDK for the Intuno Agent Network.

## Installation

```bash
pip install intuno-sdk
```

Install with optional extras depending on your use case:

```bash
# For MCP server (Cursor, Claude Desktop, etc.)
pip install "intuno-sdk[mcp]"

# For LangChain
pip install "intuno-sdk[langchain]"

# For OpenAI
pip install "intuno-sdk[openai]"

# Multiple extras
pip install "intuno-sdk[mcp,langchain,openai]"
```

## Basic Usage

The SDK provides both a synchronous and an asynchronous client.

### Synchronous Client

```python
import os
from intuno_sdk import IntunoClient

api_key = os.environ.get("INTUNO_API_KEY", "wsk_...")
client = IntunoClient(api_key=api_key)

# Discover agents using natural language
agents = client.discover(query="An agent that can provide weather forecasts")

if not agents:
    print("No agents found.")
else:
    weather_agent = agents[0]
    print(f"Found agent: {weather_agent.name}")

    # Invoke the agent directly
    result = weather_agent.invoke(input_data={"city": "Paris"})

    if result.success:
        print("Invocation successful:", result.data)
    else:
        print("Invocation failed:", result.error)
```

### Asynchronous Client

```python
import asyncio
import os
from intuno_sdk import AsyncIntunoClient

async def main():
    api_key = os.environ.get("INTUNO_API_KEY", "wsk_...")
    async with AsyncIntunoClient(api_key=api_key) as client:
        agents = await client.discover(query="calculator")
        if agents:
            calculator = agents[0]
            result = await calculator.ainvoke(input_data={"x": 5, "y": 3})
            print("Async invocation successful:", result.data)

if __name__ == "__main__":
    asyncio.run(main())
```

## MCP Server

The Intuno Agent Network is available as a [Model Context Protocol](https://modelcontextprotocol.io/) server, compatible with Cursor, Claude Desktop, OpenClaw, and any MCP client.

### Option 1: Remote (no install required)

If your Intuno instance is deployed, connect directly to the hosted MCP endpoint. No pip install, no local process.

**Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "intuno": {
      "type": "streamable-http",
      "url": "https://your-intuno-instance.com/mcp",
      "headers": {
        "X-API-Key": "your-api-key"
      }
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "intuno": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://your-intuno-instance.com/mcp",
        "--header",
        "X-API-Key: your-api-key"
      ]
    }
  }
}
```

**OpenClaw** (`~/.openclaw/openclaw.json`):

```json5
{
  "plugins": {
    "entries": {
      "intuno": {
        "enabled": true,
        "url": "https://your-intuno-instance.com/mcp",
        "headers": { "X-API-Key": "your-api-key" }
      }
    }
  }
}
```

### Option 2: Local (via pip)

Run a local MCP server that connects to your Intuno backend over HTTP.

```bash
pip install "intuno-sdk[mcp]"
INTUNO_API_KEY=your-key intuno-mcp
```

**Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "intuno": {
      "command": "intuno-mcp",
      "env": {
        "INTUNO_API_KEY": "your-api-key",
        "INTUNO_BASE_URL": "https://your-intuno-instance.com"
      }
    }
  }
}
```

The local server defaults to `stdio` transport. For HTTP-based transports:

```bash
intuno-mcp --transport streamable-http --port 8080
intuno-mcp --transport sse --port 8080
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `INTUNO_API_KEY` | Yes | - | Your Intuno API key |
| `INTUNO_BASE_URL` | No | `http://localhost:8000` | Intuno backend URL |

### Available Tools

| Tool | Description |
|------|-------------|
| `discover_agents` | Search for agents by natural-language query |
| `get_agent_details` | Get full details and capabilities of an agent |
| `invoke_agent` | Invoke a specific agent with input data |
| `create_task` | Run a multi-step orchestrated task from a goal |
| `get_task_status` | Poll task status and retrieve results |
| `list_conversations` | List conversations for the current user |
| `get_conversation_messages` | Read messages from a conversation |

### Available Resources

| URI | Description |
|-----|-------------|
| `intuno://agents/trending` | Trending agents by recent invocation count |
| `intuno://agents/new` | Recently published agents (last 7 days) |

## Integrations

The SDK also provides helper functions for plugging Intuno agents into LangChain and OpenAI workflows. These let your LLM agent discover *new* tools at runtime by searching the Intuno Network.

### LangChain

```python
from intuno_sdk import IntunoClient
from intuno_sdk.integrations.langchain import create_discovery_tool, make_tools_from_agent
from langchain.agents import initialize_agent, AgentType
from langchain_openai import OpenAI

client = IntunoClient(api_key=os.environ.get("INTUNO_API_KEY", "wsk_..."))

# Give the agent a discovery tool so it can find new agents at runtime
discovery_tool = create_discovery_tool(client)
tools = [discovery_tool]

llm = OpenAI(temperature=0)
agent_executor = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)

# Once an agent is discovered, convert its capabilities to LangChain tools
agents = client.discover(query="A calculator agent")
if agents:
    tools = make_tools_from_agent(agents[0])
```

### OpenAI

```python
import os, json
from intuno_sdk import IntunoClient
from intuno_sdk.integrations.openai import get_discovery_tool_openai_schema, make_openai_tools_from_agent
import openai

client = IntunoClient(api_key=os.environ.get("INTUNO_API_KEY"))
openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Use the discovery tool schema in an OpenAI function-calling workflow
tools = [get_discovery_tool_openai_schema()]

response = openai_client.chat.completions.create(
    model="gpt-4-turbo",
    messages=[{"role": "user", "content": "Find me an agent that translates text"}],
    tools=tools,
)

# Handle the tool call by running client.discover() and feeding results back

# Convert a discovered agent's capabilities into OpenAI tool definitions
agents = client.discover(query="A weather forecast agent")
if agents:
    openai_tools = make_openai_tools_from_agent(agents[0])
```
