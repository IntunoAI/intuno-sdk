# Network Semantics

Low-level reference for how communication networks behave. For the
quickstart, see [README](../README.md#multi-directional-networks). For
an end-to-end walkthrough, see [the tutorial](tutorials/multi_directional.md).

## Topologies

A network has a **topology** that constrains who can talk to whom.

| Topology | Who can send to whom | When to use |
|----------|----------------------|-------------|
| `mesh` (default) | Any participant → any participant | Small groups; general-purpose A2A |
| `star` | Any participant ↔ hub only | One coordinator (orchestrator) routes all traffic |
| `ring` | Participant *n* → participant *n+1* only | Pipelines; sequential handoff |
| `custom` | Caller specifies allowed edges | Enforce a domain-specific protocol |

Topology is enforced by the backend — sending a message that violates
topology returns `400 Bad Request` with `error: "topology_violation"`.
Pick the topology when you `create_network(..., topology="mesh")`; it's
immutable thereafter.

## Channel types

Each message carries a `channel_type`. The SDK wraps each type with a
dedicated method:

| Channel | Delivery model | SDK method | Backend route |
|---------|----------------|-----------|---------------|
| `call` | Synchronous; caller blocks until target responds | `network_call` | `POST /networks/{id}/call` |
| `message` | Async push to `callback_url` | `network_send` | `POST /networks/{id}/messages/send` |
| `mailbox` | Store-only; recipient polls | `send_to_mailbox` | `POST /networks/{id}/mailbox` |

### Call

- Blocks the caller for up to ~30 seconds.
- Returns a `CallResult` with `success`, `message_id`, and `response`
  (the target's payload).
- If the target has no `callback_url`, the call fails with
  `"target_unreachable"`.

### Message

- Fire-and-forget from the caller's perspective.
- Backend POSTs to the recipient's `callback_url` with the message body
  and an HMAC signature header.
- Failed deliveries are retried by a backend delivery worker with
  exponential backoff.
- Use when the recipient has a reachable `callback_url`.

### Mailbox

- No push delivery. Message is stored; recipient reads via `get_inbox`.
- Never retried because there's no delivery to fail.
- Use when the recipient runs on localhost, behind NAT, or only polls.

## Callback vs polling

Every participant is either *push-delivered* (has a `callback_url`) or
*polling* (`polling_enabled=True`). Pick based on deployment:

| | Use callback | Use polling |
|--|--------------|-------------|
| Deployment | Publicly reachable (HTTPS) | Localhost, behind NAT, no HTTPS |
| Latency | Low (push) | Depends on poll interval |
| Recommended polling cadence | N/A | 2–10 seconds for interactive UX |
| Semantics | At-least-once with retries | At-most-once, but read-your-own messages |

A participant can have *both* a callback AND polling enabled — messages
are pushed AND stored for polling. Use this during callback migrations
or when you want a safety net against callback downtime.

## Acknowledgement

Messages read via `get_inbox` are **unread by default**. Call
`acknowledge_messages(network_id, [id1, id2, ...])` to mark them as
read. Unacknowledged messages are returned again on the next
`get_inbox` call — so ack-after-processing gives you at-least-once
polling semantics.

Push-delivered messages (via `callback_url`) are considered delivered
once the callback returns `2xx`; no explicit ack is needed.

## Error codes

The SDK raises `IntunoError` for any non-2xx response. The error text
contains the backend's `detail` field. Common codes:

| Status | `detail` | Likely cause |
|--------|----------|--------------|
| 400 | `topology_violation` | Attempted a call/message not allowed by topology |
| 400 | `content_too_large` | Exceeds 64 KB content limit |
| 401 | `invalid_api_key` | Wrong or missing API key / JWT |
| 403 | `not_network_member` | Caller is not a participant in the network |
| 404 | `network_not_found` / `participant_not_found` | Wrong ID or already deleted |
| 408 | `call_timeout` | Target didn't respond within 30s |
| 409 | `duplicate_participant_name` | Name already taken in this network |
| 422 | validation failure | Bad request body (see `detail` for field) |
| 502 | `target_unreachable` | Target's `callback_url` returned 5xx or was unreachable |

## Size limits

- `content` on any channel message: **64 KB** (`MAX_CONTENT_LENGTH` on
  the backend). Exceeding returns `400 content_too_large`.
- `metadata` dict: no hard limit but kept small is polite; the backend
  serializes it as JSONB.

## Private networks

`ensure_network(caller_name, target_name)` creates or finds a
two-participant mesh network called `private-{caller}-{target}`. The
SDK uses this helper internally for the "just let me call another agent
without thinking about plumbing" case. If you need a richer topology or
more than two participants, use `create_network` + `join_network`
directly.

## See also

- [`tutorials/multi_directional.md`](tutorials/multi_directional.md) — end-to-end walkthrough.
- Backend spec: `wisdom/docs/NETWORKS.md` and `wisdom/docs/A2A.md` in
  the `IntunoAI/wisdom` repo.
