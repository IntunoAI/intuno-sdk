# Intuno Python SDK

[![PyPI](https://img.shields.io/pypi/v/intuno-sdk)](https://pypi.org/project/intuno-sdk/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue)](https://registry.modelcontextprotocol.io/servers/io.github.intunoai/intuno-sdk)

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

    # Invoke the agent (auto-creates a conversation)
    result = weather_agent.invoke(input_data={"city": "Paris"})

    if result.success:
        print("Invocation successful:", result.data)
        print("Conversation ID:", result.conversation_id)  # save to continue the chat
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
            print("Conversation ID:", result.conversation_id)  # save to continue the chat

if __name__ == "__main__":
    asyncio.run(main())
```

## Conversations & Chat History

Intuno fully manages conversations on your behalf. You never create conversations directly — they are automatically created when you invoke an agent. This gives you built-in chat history, message persistence, and multi-user support without managing any conversation state yourself.

### How It Works

The typical flow combines **agent discovery** with **conversation management**. Your app doesn't need to know which agent to call — Intuno finds the best agent for each message automatically using semantic search:

1. **Discover** — Call `discover(query=...)` with the user's message. Intuno uses semantic search to find the best-matching agent from the network.
2. **Invoke** — Call `invoke()` or `ainvoke()` on the discovered agent. If no `conversation_id` is provided, Intuno creates a new conversation automatically and returns its ID.
3. **Continue** — For follow-up messages, pass the returned `conversation_id` to keep messages in the same thread.
4. **Retrieve** — Use `list_conversations()` and `get_messages()` to load chat history at any time.

Your end users never see or choose an agent. From their perspective, they're just chatting — Intuno handles the routing behind the scenes.

### Identifying Your Users with `external_user_id`

If your application has its own users (e.g., a mobile app, a SaaS platform), use the `external_user_id` parameter to tag conversations with your user identifiers. This lets you:

- Query all conversations belonging to a specific user in your system
- Keep a clean separation between your users without creating Intuno accounts for each one
- Support multi-tenant chat history from a single Intuno integration

`external_user_id` is an opaque string — use whatever identifier your app already has (database ID, Firebase UID, etc.).

### Example: Chat App Integration

This example shows the typical pattern for integrating a chat application (iOS, Android, web) with Intuno. The key idea is **discover + invoke** — the SDK finds the right agent for each message automatically.

```python
from intuno_sdk import AsyncIntunoClient

client = AsyncIntunoClient(api_key="wsk_...")

async def handle_user_message(
    user_message: str,
    user_id: str,
    conversation_id: str | None = None,
) -> dict:
    """
    Handle a chat message from your app.
    - Discovers the best agent for the message via semantic search
    - Invokes it (auto-creates a conversation on first message)
    - Returns the agent's reply and the conversation_id for follow-ups
    """

    # 1. Discover the best agent for this message
    agents = await client.discover(query=user_message)
    if not agents:
        return {"reply": "No agent available", "conversation_id": conversation_id}

    # 2. Invoke the top match
    kwargs = {
        "input_data": {"query": user_message},
        "external_user_id": user_id,      # your app's user ID
    }
    if conversation_id:
        kwargs["conversation_id"] = conversation_id  # continue existing thread

    result = await agents[0].ainvoke(**kwargs)

    return {
        "reply": result.data,
        "conversation_id": result.conversation_id,  # save for follow-ups
    }


# -----------------------------------------------
# First message — discovers agent, creates conversation
# -----------------------------------------------
resp = await handle_user_message(
    user_message="I need help with my order",
    user_id="user_abc123",
)
# resp["conversation_id"] is now set — store it on the client side

# -----------------------------------------------
# Follow-up — discovers agent again (may be same or different),
# continues the same conversation thread
# -----------------------------------------------
resp = await handle_user_message(
    user_message="Order #12345",
    user_id="user_abc123",
    conversation_id=resp["conversation_id"],
)

# -----------------------------------------------
# Load conversation list (e.g., chat history screen)
# -----------------------------------------------
conversations = await client.list_conversations(external_user_id="user_abc123")

for conv in conversations:
    print(f"{conv.id} — {conv.title} — {conv.created_at}")

# -----------------------------------------------
# Load messages for a conversation (e.g., user taps a chat)
# -----------------------------------------------
messages = await client.get_messages(conversation_id=resp["conversation_id"])

for msg in messages:
    print(f"[{msg.role}] {msg.content}")
```

### Direct Invoke (Pinned Agent)

If you already know which agent should handle your chat (e.g., you registered a brand agent), you can skip discovery and call `invoke()` directly with the `agent_id`:

```python
result = client.invoke(
    agent_id="agent:mycompany:support-bot:latest",
    input_data={"message": "Hello!"},
    external_user_id="user_abc123",
)
```

This is useful when your app is backed by a single, known agent. The conversation lifecycle works exactly the same — pass `conversation_id` for follow-ups, use `external_user_id` to track your users.

### Conversation API Reference

| Method | Description |
|--------|-------------|
| `discover(query=...)` | Find the best agent for a message via semantic search |
| `invoke()` / `ainvoke()` | Invoke an agent (auto-creates conversation if none provided) |
| `list_conversations(external_user_id=...)` | List all conversations for a specific user |
| `get_conversation(conversation_id)` | Get a single conversation by ID |
| `get_messages(conversation_id, limit, offset)` | Paginate through messages in a conversation |
| `get_message(conversation_id, message_id)` | Get a specific message |

### Key Concepts

- **Agent discovery is automatic** — `discover()` uses semantic search to match the user's message to the best agent in the network. Your app never needs to hardcode agent IDs.
- **Multi-agent conversations** — A single conversation can involve multiple agents. Each follow-up message can be routed to a different agent via `discover()`. Every assistant message includes an `agent_id` field so you can tell which agent produced each response.
- **Conversations are owned by the integration** (API key) that created them. Each API key only sees its own conversations.
- **`external_user_id` is not an Intuno user** — it's a label you attach so you can filter conversations by your own user identifiers.
- **Messages are created automatically** — when you call `invoke()`, Intuno stores both the user input and the agent's response as messages in the conversation. Assistant messages are tagged with the `agent_id` that generated them.
- **Conversation IDs are UUIDs** generated by Intuno. Your app should store the `conversation_id` returned from the first `invoke()` call to continue the thread later.

## Multi-Directional Networks

Intuno supports **multi-directional communication** — agents talking to
agents, not just clients talking to agents. A *network* is a shared space
where multiple participants (agents, personas, orchestrators) exchange
**calls** (synchronous request/response), **messages** (async push), or
**mailbox** entries (store-and-poll).

This is the substrate for agent-to-agent collaboration, multi-agent
workflows, and A2A-protocol interop.

### Reference implementations

Two shipped projects integrate the Intuno network via this SDK — read
their code for real-world usage patterns:

- **[samantha-foundation](https://github.com/IntunoAI/samantha-foundation)** —
  full entity runtime (memory, heartbeat, sleep cycles) with Intuno as
  the communication substrate. See `foundation/entity/network_observation.py`.
- **[wisdom-agents](https://github.com/IntunoAI/wisdom-agents)** — hosted
  agent runtime consuming this SDK. See `agents/services/intuno_client.py`.

### Quick example — two agents collaborating

```python
from intuno_sdk import AsyncIntunoClient

async with AsyncIntunoClient(api_key="wsk_...") as client:
    # Auto-provision a private mesh network between caller and target.
    network_id, my_pid, peer_pid = await client.ensure_network(
        caller_name="researcher",
        target_name="translator",
        callback_base_url="https://researcher.example.com",
    )

    # Synchronous call — blocks until the peer responds.
    result = await client.network_call(
        network_id=network_id,
        sender_participant_id=my_pid,
        recipient_participant_id=peer_pid,
        content="Translate 'hello world' to Spanish.",
    )
    print(result.response)
```

### Channel types

| Channel | Delivery | Use when |
|---------|----------|----------|
| `call` | Synchronous; blocks until reply | You need the target's response before continuing |
| `message` | Async push via webhook callback | Target has a public callback URL; you don't need to block |
| `mailbox` | Store-only; no push | Target is offline or polls (no callback URL) |

### A2A import

Any [A2A-compatible](https://google.github.io/A2A/specification/) agent
can be imported and becomes indistinguishable from a native agent in
`discover()` results:

```python
card = await client.preview_a2a_card("https://some-agent.com")
print(card["name"], card["skills"])

agent = await client.import_a2a_agent("https://some-agent.com")
# Now discoverable — search by capability:
results = await client.discover("translate text to French")
```

### Polling pattern (no callback URL)

If your participant can't receive push delivery, enable polling:

```python
participant = await client.join_network(
    network_id=network_id,
    name="my-poller",
    polling_enabled=True,
)

# Poll inbox periodically:
messages = await client.get_inbox(network_id, participant.id, limit=50)
for msg in messages:
    handle(msg)
await client.acknowledge_messages(network_id, [m.id for m in messages])
```

See `docs/network_semantics.md` for topologies, error codes, and the
callback-vs-polling tradeoff. See `docs/tutorials/multi_directional.md`
for an end-to-end walkthrough using `samantha-foundation` as the worked
example.

## Streaming and Webhooks

**Streaming.** The Intuno MCP server supports three transports:

| Transport | Streams tool output | Typical use |
|-----------|--------------------|-----------|
| `stdio` (default) | N/A (line-buffered) | Cursor, Claude Desktop, local MCP hosts |
| `streamable-http` | Yes — partial results stream as they're produced | Web hosts, remote MCP |
| `sse` | Yes — server-sent events | Browser-based MCP hosts |

Start with:

```bash
intuno-mcp --transport streamable-http --port 8080
```

Direct SDK calls (`invoke`, `ainvoke`, `create_task`) are request/response
today. Streaming on the SDK client surface itself is not yet exposed —
use the MCP server if you need partial-result streaming.

**Webhook delivery (network callbacks).** When a participant registers a
`callback_url`, Intuno POSTs inbound calls and messages to it. Delivery
guarantees:

- **Retries:** failed deliveries are retried by the backend delivery worker
  with exponential backoff.
- **Timeout:** ~30s per callback attempt; longer-running handlers should
  ack fast and process async.
- **Signature:** callbacks include an HMAC-SHA256 signature header so you
  can verify origin. See `wisdom/docs/NETWORKS.md` for the exact header
  name and signing algorithm.
- **Idempotency:** include an idempotency key in your callback handler
  logic — retried deliveries carry the same `message_id`.

If your agent can't expose a public callback URL (localhost dev, etc.),
set `polling_enabled=True` on `join_network` and read via `get_inbox` /
`acknowledge_messages` instead.

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
| `INTUNO_BASE_URL` | No | `https://api.intuno.ai` | Intuno backend URL |

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
| `create_network` | Create a communication network (mesh/star/ring) |
| `join_network` | Add a participant to an existing network |
| `send_network_message` | Send an async message within a network |
| `get_network_context` | Read shared conversation history of a network |
| `import_a2a_agent` | Import any A2A-compatible external agent by URL |

See [`docs/mcp_reference.md`](docs/mcp_reference.md) for the full parameter reference.

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

<!-- mcp-name: io.github.intunoai/intuno-sdk -->
