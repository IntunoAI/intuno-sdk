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

    # Invoke by capability name
    result = weather_agent.invoke(
        capability_name_or_id="get_forecast",
        input_data={"city": "Paris"}
    )

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
            result = await calculator.ainvoke(
                capability_name_or_id="add",
                input_data={"x": 5, "y": 3}
            )
            print("Async invocation successful:", result.data)

if __name__ == "__main__":
    asyncio.run(main())
```

## MCP Server

The SDK includes a built-in [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes the Intuno Agent Network to any MCP-compatible AI assistant (Cursor, Claude Desktop, etc.).

### Quick Start

```bash
pip install "intuno-sdk[mcp]"
```

Run the server:

```bash
INTUNO_API_KEY=your-key intuno-mcp
```

Or with `python -m`:

```bash
INTUNO_API_KEY=your-key python -m intuno_sdk.mcp_server
```

### Available Tools

| Tool | Description |
|------|-------------|
| `discover_agents` | Search for agents by natural-language query |
| `get_agent_details` | Get full details and capabilities of an agent |
| `invoke_agent` | Invoke a specific agent capability with input data |
| `create_task` | Run a multi-step orchestrated task from a goal |
| `get_task_status` | Poll task status and retrieve results |

### Available Resources

| URI | Description |
|-----|-------------|
| `intuno://agents/trending` | Trending agents by recent invocation count |
| `intuno://agents/new` | Recently published agents (last 7 days) |

### Cursor Configuration

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "intuno": {
      "command": "intuno-mcp",
      "env": {
        "INTUNO_API_KEY": "your-api-key",
        "INTUNO_BASE_URL": "https://your-wisdom-instance.com"
      }
    }
  }
}
```

### Transport Options

The server defaults to `stdio` (standard for Cursor/Claude Desktop). For HTTP-based transports:

```bash
# Streamable HTTP
INTUNO_API_KEY=your-key intuno-mcp --transport streamable-http --port 8080

# SSE
INTUNO_API_KEY=your-key intuno-mcp --transport sse --port 8080
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `INTUNO_API_KEY` | Yes | - | Your Intuno API key |
| `INTUNO_BASE_URL` | No | `http://localhost:8000` | Wisdom backend URL |

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
