# Changelog

All notable changes to `intuno-sdk` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — 2026-04-22

### Added

- **Complete sync client parity.** `IntunoClient` now exposes every network
  and A2A method that was previously async-only: `create_network`,
  `list_networks`, `get_network`, `delete_network`, `join_network`,
  `list_participants`, `leave_network`, `network_call`, `network_send`,
  `network_messages`, `send_to_mailbox`, `get_inbox`, `acknowledge_messages`,
  `get_network_context`, `ensure_network`.
- **A2A agent import.** `preview_a2a_card(url)`, `import_a2a_agent(url)`,
  and `refresh_a2a_agent(agent_id)` on both sync and async clients. Import
  any A2A-compatible external agent into Intuno; the imported agent is
  indistinguishable from natively registered agents in `discover()` results.
- **Mailbox / inbox / ack.** `send_to_mailbox`, `get_inbox`, and
  `acknowledge_messages` for store-and-poll patterns (use when a recipient
  has no public callback URL).
- **Shared network context.** `get_network_context(network_id)` returns
  recent cross-participant messages — useful for late-joining participants
  and summarization.
- **MCP server — network tools.** The `intuno-mcp` server exposes
  `create_network`, `join_network`, `send_network_message`,
  `get_network_context`, and `import_a2a_agent` as MCP tools, so any MCP
  host (Cursor, Claude Desktop, etc.) can orchestrate multi-agent networks.
- **LangChain network tools.** `create_network_tools(client, agent_name)`
  returns `intuno_call_agent`, `intuno_send_message`, and
  `intuno_import_a2a_agent` as LangChain `Tool` objects.
- **OpenAI A2A tools.** `get_a2a_tools()` returns OpenAI function-calling
  schemas for `intuno_preview_a2a_card` and `intuno_import_a2a_agent`.
  `execute_network_tool` now handles both.
- **Examples directory.** Runnable scripts under `examples/` for discovery,
  network calls, polling, MCP, and chat-app integration patterns.
- **Documentation.** `docs/network_semantics.md` (message ack,
  topologies, error codes), `docs/mcp_reference.md` (full tool + resource
  list), `docs/tutorials/multi_directional.md` (end-to-end walkthrough
  using `samantha-foundation` as the worked example), `docs/RELEASING.md`
  (cross-repo version policy).
- `CHANGELOG.md` (this file).

### Changed

- README covers multi-directional networks, streaming transport notes,
  and webhook delivery guarantees. `samantha-foundation` and `wisdom-agents`
  are called out as reference integrations.

## [0.3.0] — 2026-04-15

### Added

- Anthropic / Claude integration (`intuno_sdk.integrations.anthropic`).
- JWT bearer token auth (in addition to API keys). Tokens beginning with
  `eyJ` are sent as `Authorization: Bearer`; all others as `X-API-Key`.
- Async communication network primitives: `create_network`, `list_networks`,
  `join_network`, `list_participants`, `network_call`, `network_send`,
  `network_messages`, `ensure_network`.
- OpenAI-ready network tools: `get_network_tools()` with `intuno_discover`,
  `intuno_call_agent`, `intuno_send_message`, and `execute_network_tool`
  handler.

## [0.2.2] — 2026-03

### Added

- `create_task` tool schema for OpenAI and LangChain integrations.

## [0.2.1] — 2026-02

### Changed

- Version bump; CI / publish pipeline stabilization.

## [0.2.0] — 2026-02

### Added

- Orchestrator (`create_task`, `get_task`).
- MCP server (`intuno-mcp` entry point; stdio, SSE, streamable-http
  transports).
- Model Context Protocol license and registry metadata.
- Publish workflow.

## [0.1.1] — 2026-01

### Fixed

- Pre-publish fixes: README examples, version sync, LangChain compatibility,
  request timeouts.

## [0.1.0] — 2026-01

### Added

- Initial public release. Sync and async clients for agent discovery
  (`discover`), invocation (`invoke` / `ainvoke`), conversations
  (`list_conversations`, `get_messages`), and LangChain / OpenAI
  integration helpers.

[0.4.0]: https://github.com/IntunoAI/intuno-sdk/releases/tag/v0.4.0
[0.3.0]: https://github.com/IntunoAI/intuno-sdk/releases/tag/v0.3.0
[0.2.2]: https://github.com/IntunoAI/intuno-sdk/releases/tag/v0.2.2
[0.2.1]: https://github.com/IntunoAI/intuno-sdk/releases/tag/v0.2.1
[0.2.0]: https://github.com/IntunoAI/intuno-sdk/releases/tag/v0.2.0
[0.1.1]: https://github.com/IntunoAI/intuno-sdk/releases/tag/v0.1.1
[0.1.0]: https://github.com/IntunoAI/intuno-sdk/releases/tag/v0.1.0
