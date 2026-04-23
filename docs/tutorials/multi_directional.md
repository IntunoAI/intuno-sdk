# Tutorial: Integrating Intuno End-to-End

A narrative walkthrough of how to build an agent that participates in
the Intuno multi-directional network. We use **real shipped code** from
two reference integrations rather than toy examples:

- [`samantha-foundation/foundation/entity/network_observation.py`](https://github.com/IntunoAI/samantha-foundation/blob/main/foundation/entity/network_observation.py) —
  the OSS entity runtime's network participation layer.
- [`wisdom-agents/agents/services/intuno_client.py`](https://github.com/IntunoAI/wisdom-agents/blob/main/agents/services/intuno_client.py) —
  the hosted runtime's SDK wrapper.

Read alongside those files; this tutorial tells you *why* each step exists.

## What you'll build

An agent that:

1. Registers itself on the Intuno network.
2. Provisions a private mesh with another agent and makes a synchronous
   call.
3. Receives inbound calls via a webhook callback.
4. Falls back to polling when it can't expose a callback URL.
5. Logs its network activity for observability.

## Prerequisites

```bash
pip install "intuno-sdk[mcp]"
```

You need `INTUNO_API_KEY` (or a JWT bearer token) and `INTUNO_BASE_URL`
if self-hosted.

## 1. Register (and what "register" actually means)

The SDK has no explicit `register_agent` call — registration is
**implicit on first invocation**. When a consumer calls your agent, the
broker creates the conversation and routes the call; there's no step
you need to run yourself.

What you *do* need to do explicitly is **join a network** to participate
in multi-directional comms:

```python
from intuno_sdk import AsyncIntunoClient

client = AsyncIntunoClient(api_key=os.environ["INTUNO_API_KEY"])
```

## 2. `ensure_network` + join

The `ensure_network` helper is the "just let me talk to this other
agent" escape hatch — it creates a private two-participant mesh if one
doesn't exist, and returns the IDs you need to send messages:

```python
network_id, my_participant_id, peer_participant_id = await client.ensure_network(
    caller_name="my-research-agent",
    target_name="translator",
    callback_base_url="https://research.example.com",  # where Intuno POSTs inbound
)
```

See the `_ensure_private_network_*` methods in
`samantha-foundation` for the same pattern applied to entity ↔ agent
collaboration.

For richer topologies (e.g., a four-agent star), call `create_network`
and `join_network` directly. The private-network helper is a
convenience for 1:1.

## 3. Inbound via `network_call` callback

When a peer calls you via `network_call`, Intuno POSTs to the callback
URL you registered. The payload schema is documented at
[`samantha-foundation/docs/a2a_payload.md`](https://github.com/IntunoAI/samantha-foundation/blob/main/docs/a2a_payload.md)
(generated from the same backend route).

Minimal FastAPI handler:

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/agents/my-research-agent/callback")
async def callback(req: Request):
    payload = await req.json()
    # payload has: channel_type, sender_participant_id, content, metadata, message_id, ...
    user_msg = payload["content"]
    reply = await do_the_work(user_msg)
    return {"response": reply}   # returned synchronously for channel_type="call"
```

`wisdom-agents/agents/routes/network_callback.py` is the production
version with:

- HMAC signature verification (production deployments — don't skip).
- Per-channel-type branching (`call` returns synchronously; `message`
  acks and processes async).
- Logging hooks and metrics.
- Entity-level routing (multiple entities share one process).

Read that file when you're ready to harden.

## 4. Outbound via `network_send`

Fire-and-forget:

```python
await client.network_send(
    network_id=network_id,
    sender_participant_id=my_participant_id,
    recipient_participant_id=peer_participant_id,
    content="heads up: the batch finished at 14:03",
)
```

Synchronous reply required:

```python
result = await client.network_call(
    network_id=network_id,
    sender_participant_id=my_participant_id,
    recipient_participant_id=peer_participant_id,
    content="What's the right translation for 'invoice'?",
)
print(result.response)   # the peer's reply
```

Rule of thumb: use `network_call` when you'd otherwise block waiting for
a reply; use `network_send` for notifications, status updates, or when
the peer's reply (if any) will arrive later as its own inbound call.

## 5. Polling fallback

When you can't expose a public callback URL (local dev, NAT, no HTTPS),
enable polling on join:

```python
participant = await client.join_network(
    network_id=network_id,
    name="my-laptop-agent",
    polling_enabled=True,
)

# Every few seconds:
messages = await client.get_inbox(network_id, participant.id, limit=50)
for m in messages:
    await handle(m)

# Ack so you don't see them again:
await client.acknowledge_messages(network_id, [m.id for m in messages])
```

The `samantha-foundation` entity uses polling when `AGENTS_BASE_URL` is
unset (typical during local development). The same code path runs on
both laptop and production — only the participant-join config differs.

## 6. Observability

Both reference implementations log three things at minimum:

1. **On join:** network ID, participant ID, whether callback or polling.
2. **On each inbound:** `message_id`, sender, channel type, latency from
   timestamp to now.
3. **On each outbound:** same shape, plus the message status returned
   from `network_send`.

This is enough to answer "did the message get there" and "how long did
the peer take to respond." For Samantha's implementation, see the
`logger.info(...)` sites in `network_observation.py`.

## Where to go next

- **A2A import:** pull any A2A-compatible external agent into the same
  network with `client.import_a2a_agent(url)`. See README §
  "Multi-Directional Networks > A2A import".
- **Error handling:** `docs/network_semantics.md` documents every error
  code and the topology constraints that produce them.
- **Real code:** open `samantha-foundation/foundation/entity/` and read.
  The entity/network integration is ~200 lines of real production code.
