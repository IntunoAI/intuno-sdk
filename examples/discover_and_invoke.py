"""Discover an agent by capability and invoke it.

Run:
    INTUNO_API_KEY=wsk_... python examples/discover_and_invoke.py
"""

import os

from intuno_sdk import IntunoClient


def main() -> None:
    api_key = os.environ.get("INTUNO_API_KEY")
    if not api_key:
        raise SystemExit("Set INTUNO_API_KEY in your environment.")

    with IntunoClient(api_key=api_key) as client:
        agents = client.discover(query="translate English text to Spanish", limit=3)
        if not agents:
            print("No matching agents found.")
            return

        for i, a in enumerate(agents, 1):
            score = f"{a.similarity_score:.3f}" if a.similarity_score else "—"
            print(f"{i}. {a.name} ({a.agent_id}) similarity={score}")

        top = agents[0]
        print(f"\nInvoking top match: {top.name}")

        result = top.invoke(input_data={"text": "Hello, world!"})
        if result.success:
            print("Result:", result.data)
            print("Conversation:", result.conversation_id)
        else:
            print("Invocation failed:", result.error)


if __name__ == "__main__":
    main()
