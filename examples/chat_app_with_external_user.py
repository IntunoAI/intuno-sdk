"""The typical chat-app integration pattern — discover + invoke, scoped to an
external user.

The point of ``external_user_id`` is that your app already has its own users
(Firebase UIDs, DB rows, whatever). Pass that ID through and Intuno scopes
conversations and history by it without creating an Intuno account per user.

Run:
    INTUNO_API_KEY=wsk_... python examples/chat_app_with_external_user.py
"""

import asyncio
import os

from intuno_sdk import AsyncIntunoClient


async def handle_message(
    client: AsyncIntunoClient,
    user_message: str,
    user_id: str,
    conversation_id: str | None = None,
) -> dict:
    """Discover the best agent for this message, invoke it, and return the reply."""
    agents = await client.discover(query=user_message, limit=1)
    if not agents:
        return {"reply": None, "conversation_id": conversation_id}

    kwargs: dict = {
        "input_data": {"query": user_message},
        "external_user_id": user_id,
    }
    if conversation_id:
        kwargs["conversation_id"] = conversation_id

    result = await agents[0].ainvoke(**kwargs)
    return {
        "reply": result.data,
        "conversation_id": result.conversation_id,
    }


async def main() -> None:
    api_key = os.environ.get("INTUNO_API_KEY")
    if not api_key:
        raise SystemExit("Set INTUNO_API_KEY in your environment.")

    async with AsyncIntunoClient(api_key=api_key) as client:
        user_id = "demo_user_42"

        # First message — Intuno discovers an agent and creates a conversation.
        r1 = await handle_message(client, "I need help with my order", user_id)
        print("Reply 1:", r1["reply"])
        conversation_id = r1["conversation_id"]

        # Follow-up — Intuno may route to a different agent; the conversation
        # stays the same thread.
        r2 = await handle_message(client, "Order #12345", user_id, conversation_id)
        print("Reply 2:", r2["reply"])

        # List this user's conversations (e.g., for a chat history screen).
        conversations = await client.list_conversations(external_user_id=user_id)
        print(f"\nUser has {len(conversations)} conversation(s):")
        for c in conversations[:5]:
            print(f"  {c.id} — {c.title} — {c.created_at}")

        # Load the last conversation's messages.
        if conversation_id:
            messages = await client.get_messages(conversation_id=conversation_id)
            print(f"\n{conversation_id} — {len(messages)} message(s):")
            for m in messages:
                print(f"  [{m.role}] {m.content}")


if __name__ == "__main__":
    asyncio.run(main())
