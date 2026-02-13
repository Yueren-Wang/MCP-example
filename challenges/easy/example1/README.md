# Challenge 1: Basic Prompt Injection

This challenge demonstrates a simple prompt injection vulnerability in an MCP server. The server doesn't properly validate user input, allowing attackers to inject malicious instructions that the LLM will execute.

## Vulnerability

The MCP server exposes a resource that contains user-provided content without proper validation or sanitization. This allows an attacker to inject instructions that can manipulate the LLM's behavior.

## Objective

Your goal is to inject instructions that make the LLM reveal sensitive information that should be protected.

## Hints

1. Look at how user input is handled in the `notes` resource
2. Try to craft input that would make an LLM ignore its previous instructions
3. The server contains a hidden resource with sensitive information

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the vulnerable MCP server:
   ```
   python server.py
   ```

3. Connect to the server using an MCP client (e.g., Claude Desktop or the MCP Inspector)

## Difficulty

Easy
