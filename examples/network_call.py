"""Provision a private mesh network and make a synchronous call to another agent.

Uses ``ensure_network`` — the "just let me call that agent" helper. It creates
a two-participant network if one doesn't exist and returns the IDs you need.

Run:
    INTUNO_API_KEY=wsk_... python examples/network_call.py
"""

import asyncio
import os

from intuno_sdk import AsyncIntunoClient


async def main() -> None:
    api_key = os.environ.get("INTUNO_API_KEY")
    if not api_key:
        raise SystemExit("Set INTUNO_API_KEY in your environment.")

    # Find a target agent by capability.
    async with AsyncIntunoClient(api_key=api_key) as client:
        agents = await client.discover("translate text", limit=3)
        if not agents:
            print("No translator agents found.")
            return

        target = agents[0]
        print(f"Target: {target.name} ({target.agent_id})")

        # Auto-provision a private mesh between the caller and target.
        # For a public callback URL, set callback_base_url; for local dev,
        # you can skip it and rely on the target having its own callback.
        network_id, my_pid, target_pid = await client.ensure_network(
            caller_name="example-caller",
            target_name=target.name,
            caller_type="persona",  # persona = polling; agent = callback-delivered
            target_agent_id=target.id,
        )
        print(f"Network {network_id}: me={my_pid} target={target_pid}")

        # Synchronous call — blocks up to ~30s for the reply.
        result = await client.network_call(
            network_id=network_id,
            sender_participant_id=my_pid,
            recipient_participant_id=target_pid,
            content="Please translate 'good morning' to Spanish.",
        )

        if result.success:
            print("Reply:", result.response)
        else:
            print("Call failed.")


if __name__ == "__main__":
    asyncio.run(main())
