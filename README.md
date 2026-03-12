# Intuno Python SDK

The official Python SDK for the Intuno Agent Network.

## Installation

```bash
pip install intuno-sdk
```

For integrations with LangChain or OpenAI, you can install the necessary extras:
```bash
# For LangChain
pip install "intuno-sdk[langchain]"

# For OpenAI
pip install "intuno-sdk[openai]"

# For both
pip install "intuno-sdk[langchain,openai]"
```

## Basic Usage

The SDK provides both a synchronous and an asynchronous client.

### Synchronous Client

Use the `IntunoClient` for synchronous operations.

```python
import os
from intuno_sdk import IntunoClient

# It's recommended to load the API key from environment variables
api_key = os.environ.get("INTUNO_API_KEY", "wsk_...")
client = IntunoClient(api_key=api_key)

# Discover agents using natural language
agents = client.discover(query="An agent that can provide weather forecasts")

if not agents:
    print("No agents found.")
else:
    weather_agent = agents[0]
    print(f"Found agent: {weather_agent.name}")

    # Invoke by capability name. The SDK will find the correct ID.
    # Assuming the agent has a capability named "get_forecast".
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

For use with `asyncio`, use the `AsyncIntunoClient`.

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
            # Invoke by capability name. The SDK will find the correct ID.
            result = await calculator.ainvoke(
                capability_name_or_id="add",
                input_data={"x": 5, "y": 3}
            )
            print("Async invocation successful:", result.data)

if __name__ == "__main__":
    asyncio.run(main())
```

## Integrations

To build a truly autonomous agent, the agent must be able to find *new* tools on its own. The Intuno SDK provides a "discovery tool" that you can give to your LLM agent, allowing it to search the Intuno Network for other agents at runtime.

### Autonomous Discovery with LangChain

The `create_discovery_tool` function returns a `Tool` that your LangChain agent can use.

```python
from intuno_sdk import IntunoClient
from intuno_sdk.integrations.langchain import create_discovery_tool
from langchain.agents import initialize_agent, AgentType
from langchain_openai import OpenAI

client = IntunoClient(api_key=os.environ.get("INTUNO_API_KEY", "wsk_..."))

# Create the discovery tool and add it to the agent's tool list
discovery_tool = create_discovery_tool(client)
tools = [discovery_tool] # Add any other baseline tools here

llm = OpenAI(temperature=0)
agent_executor = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)

# Now the agent can decide to use the discovery tool on its own
# agent_executor.run("I need to find an agent that can calculate currency exchange rates.")
```

### Autonomous Discovery with OpenAI

The `get_discovery_tool_openai_schema` function provides the JSON schema for the discovery tool. Your code is then responsible for handling the tool call by running `client.discover()` and feeding the results back to the LLM.

Here is a complete, end-to-end example of the discovery workflow:

```python
import os
import json
from intuno_sdk import IntunoClient
from intuno_sdk.integrations.openai import get_discovery_tool_openai_schema
import openai

# 1. Initialize clients
# Make sure INTUNO_API_KEY and OPENAI_API_KEY are set in your environment
client = IntunoClient(api_key=os.environ.get("INTUNO_API_KEY"))
openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 2. Define the tools for the LLM, including the discovery tool
messages = [{"role": "user", "content": "I need to translate 'hello' to French. Can you find a tool for that?"}]
tools = [get_discovery_tool_openai_schema()]

# 3. First call to the LLM to see if it uses a tool
print("--- First API Call: Asking the LLM to find a tool ---")
response = openai_client.chat.completions.create(
    model="gpt-4-turbo",
    messages=messages,
    tools=tools,
)

response_message = response.choices[0].message
tool_calls = response_message.tool_calls

# 4. Check if the LLM decided to use the discovery tool
if not tool_calls:
    print("The LLM did not use the discovery tool.")
else:
    print("\n--- LLM decided to use the discovery tool ---")
    # Add the assistant's response to the message history
    messages.append(response_message)

    # 5. Execute the tool call(s)
    for tool_call in tool_calls:
        if tool_call.function.name == "intuno_agent_discovery":
            print(f"Executing discovery with query: {tool_call.function.arguments}")
            args = json.loads(tool_call.function.arguments)
            
            # Call the actual discovery method from the Intuno SDK
            discovered_agents = client.discover(query=args["query"])
            
            # Format the results to send back to the LLM
            discovery_result = f"Found {len(discovered_agents)} agent(s).\n"
            for agent in discovered_agents:
                cap_names = [cap.name for cap in agent.capabilities]
                discovery_result += f"- Agent: {agent.name}, Description: {agent.description}, Capabilities: {cap_names}\n"

            print(f"Discovery result: {discovery_result}")
            
            # 6. Append the tool's output to the message history
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": discovery_result,
                }
            )

    # 7. Second call to the LLM with the discovery results
    print("\n--- Second API Call: Sending discovery results back to LLM ---")
    second_response = openai_client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages,
    )
    
    print("\n--- Final LLM Response ---")
    print(second_response.choices[0].message.content)
```

### Converting Discovered Agents to Tools

Once your agent has discovered another agent, you can use the `make_tools_from_agent` (LangChain) or `make_openai_tools_from_agent` (OpenAI) helpers to convert its capabilities into usable tools for the next step of the agent's reasoning process.

#### LangChain

```python
from intuno_sdk import IntunoClient
from intuno_sdk.integrations.langchain import make_tools_from_agent
from langchain.agents import initialize_agent, AgentType
from langchain_openai import OpenAI

# Assume client is an initialized IntunoClient
agents = client.discover(query="A calculator agent")
if agents:
    calculator_agent = agents[0]
    tools = make_tools_from_agent(calculator_agent)

    print(f"Generated {len(tools)} tools for agent '{calculator_agent.name}'.")
    print(f"Tool name: {tools[0].name}")
    print(f"Tool description: {tools[0].description}")

    # These tools can now be used in a LangChain agent
    llm = OpenAI(temperature=0)
    agent_executor = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)
    agent_executor.run("What is 5 + 7?")
```

#### OpenAI

```python
from intuno_sdk import IntunoClient
from intuno_sdk.integrations.openai import make_openai_tools_from_agent
import openai

# Assume client is an initialized IntunoClient
agents = client.discover(query="A weather forecast agent")
if agents:
    weather_agent = agents[0]
    openai_tools = make_openai_tools_from_agent(weather_agent)

    print(f"Generated {len(openai_tools)} OpenAI tools for agent '{weather_agent.name}'.")
    print(openai_tools[0])

    # You can now use this list in a call to the OpenAI API
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": "What is the weather like in Boston?"}],
        tools=openai_tools,
    )
```
