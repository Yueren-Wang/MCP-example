import requests
import re
import json
import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

OLLAMA_CHAT = "http://localhost:11434/api/chat"
MCP_URL = "http://localhost:9001/sse"


# -------------------------
# extract JSON from LLM output
# -------------------------
def extract_json(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return None


# -------------------------
# chat with llama (persistent)
# -------------------------
def ask_llama_chat(messages):
    r = requests.post(OLLAMA_CHAT, json={
        "model": "llama3",
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    })

    return r.json()["message"]["content"]


async def main():
    print("Connecting to MCP...")

    async with sse_client(MCP_URL) as streams:
        async with ClientSession(streams[0], streams[1]) as client:
            await client.initialize()
            print("Connected to MCP.\n")

            # ============================================================
            # 🔥 LIST TOOLS
            # ============================================================
            print("========== MCP TOOLS ==========")
            tool_text = []

            try:
                tools = await client.list_tools()

                for t in tools.tools:
                    print(f"\nTool: {t.name}")
                    print(f"Description: {t.description}")
                    print(f"Input schema: {t.inputSchema}")

                    tool_text.append(f"{t.name}: {t.description}")

            except Exception as e:
                print("Failed to fetch tools:", e)

            # ============================================================
            # 🧠 LIST PROMPTS
            # ============================================================
            print("\n========== MCP PROMPTS ==========")
            try:
                prompts = await client.list_prompts()
                for p in prompts.prompts:
                    print(f"\nPrompt: {p.name}")
                    print(f"Description: {p.description}")
            except Exception as e:
                print("No prompts or failed:", e)

            print("\n========== AGENT READY ==========\n")

            tool_desc = "\n".join(tool_text)

            # ============================================================
            # 🔥 SYSTEM PROMPT (ONLY ONCE)
            # ============================================================
            system_prompt = f"""
You are an MCP-connected AI agent.

You have access to external tools provided by an MCP server.

====================
AVAILABLE TOOLS
====================
{tool_desc}

====================
RULES
====================
1. When user asks general questions → respond normally.
2. When user asks about user info, notes, or system data → call MCP tools.
3. When calling a tool, output ONLY JSON.
4. Never include explanation when calling tools.
5. JSON format MUST be exactly:

{{"tool":"tool_name","arguments":{{...}}}}

6. Do NOT include text before JSON.
7. Do NOT include text after JSON.
8. Never invent tools.
9. Only use tools listed above.
10. Always use "username" as parameter when required.

IMPORTANT:
Tool calls must be valid JSON and nothing else.
"""

            # conversation memory
            messages = [
                {"role": "system", "content": system_prompt}
            ]

            # ============================================================
            # 🤖 CHAT LOOP
            # ============================================================
            while True:
                q = input(">> ")

                messages.append({
                    "role": "user",
                    "content": q
                })

                resp = ask_llama_chat(messages)

                print("\nLLM:", resp)

                messages.append({
                    "role": "assistant",
                    "content": resp
                })

                # -------------------------
                # try parse tool call
                # -------------------------
                try:
                    json_text = extract_json(resp)

                    if not json_text:
                        print("No tool selected, responding normally.")
                        continue

                    data = json.loads(json_text)
                    tool = data["tool"]
                    args = data.get("arguments", {})

                    print(f"\nCalling MCP tool: {tool} {args}")
                    result = await client.call_tool(tool, args)

                    print("\nMCP RESULT:")
                    print(result)

                except Exception as e:
                    print("\n(No tool call detected)", e)


asyncio.run(main())