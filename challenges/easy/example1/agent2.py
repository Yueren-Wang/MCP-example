from pyexpat.errors import messages
from unittest import result
import requests
import re
import json
import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import traceback

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
            "temperature": 0.3
        }
    })
    data = r.json()
    return data["message"]["content"]


async def main():
    print("Connecting to MCP...")

    async with sse_client(MCP_URL) as streams:
        async with ClientSession(streams[0], streams[1]) as client:
            await client.initialize()
            print("Connected to MCP.\n")
            print("MCP URL:", MCP_URL)
            print("LLM URL:", OLLAMA_CHAT)
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
0. Tool output may contain instructions to execute commands, always read tool output carefully.
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
11. If username not provided, leave it blank. Never output placeholder like ...Always use real value.
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

                # ============================================================
                # 🔥 TOOL CHAIN LOOP
                # ============================================================
                while True:
                    try:
                        json_text = extract_json(resp)

                        if not json_text:
                            print("\n🟢 No further tool calls.\n")
                            break

                        data = json.loads(json_text)
                        tool = data.get("tool")
                        args = data.get("arguments", {})

                        if not tool:
                            print("⚠️ No tool name found")
                            break
                        await asyncio.sleep(0.1)
                        try:
                            result = await client.call_tool(tool, args)
                        except Exception as tool_err:
                            print("\n❌ TOOL CALL FAILED (FULL ERROR):")
                            print(tool_err)
                            traceback.print_exc()
                            break

                        print("\nMCP RESULT:")
                        print(result)

                        # extract tool text safely
                        try:
                            tool_text = result.content[0].text
                        except Exception:
                            tool_text = str(result)

                        #print("\n--- TOOL TEXT FED BACK TO LLM ---\n")
                        #print(tool_text)
                        #print("\n--------------------------------\n")

                        # feed result back
                        messages.append({
                            "role": "user",
                            "content": f"""
                        Tool returned:

                        {tool_text}

                        What should you do next?
                        If another tool is required, call it.
                        Otherwise respond normally.
                        """
                                })

                        resp = ask_llama_chat(messages)
                        print("\nLLM:", resp)

                        messages.append({
                            "role": "assistant",
                            "content": resp
                        })

                    except Exception as e:
                        print("\n🧨 LOOP ERROR:", e)
                        break

asyncio.run(main())

