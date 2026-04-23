"""Polling participant pattern — receive messages without exposing a callback URL.

Use this when your agent runs on localhost, behind NAT, or without HTTPS.
Enable ``polling_enabled=True`` on join; then read via ``get_inbox`` and
acknowledge with ``acknowledge_messages``.

Run:
    INTUNO_API_KEY=wsk_... python examples/network_polling.py
"""

import asyncio
import os

from intuno_sdk import AsyncIntunoClient


POLL_INTERVAL_SECONDS = 5


async def main() -> None:
    api_key = os.environ.get("INTUNO_API_KEY")
    if not api_key:
        raise SystemExit("Set INTUNO_API_KEY in your environment.")

    async with AsyncIntunoClient(api_key=api_key) as client:
        # Reuse or create a network for this demo.
        network = await client.create_network(name="polling-demo")
        print(f"Created network {network.id}")

        participant = await client.join_network(
            network_id=network.id,
            name="poller-1",
            participant_type="persona",
            polling_enabled=True,
        )
        print(f"Joined as {participant.id} (polling)")

        print(f"Polling every {POLL_INTERVAL_SECONDS}s — Ctrl-C to stop.")
        try:
            while True:
                messages = await client.get_inbox(
                    network_id=network.id,
                    participant_id=participant.id,
                    limit=50,
                )
                if messages:
                    for m in messages:
                        print(f"  [{m.channel_type}] {m.content!r}")
                    count = await client.acknowledge_messages(
                        network_id=network.id,
                        message_ids=[m.id for m in messages],
                    )
                    print(f"  Acked {count} message(s).")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nStopping.")


if __name__ == "__main__":
    asyncio.run(main())
