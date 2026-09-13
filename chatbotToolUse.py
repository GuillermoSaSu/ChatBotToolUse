"""
Chatbot with tool use (function calling).

Learning project. New concept vs. previous ones: so far Claude only
generated text. Here, Claude can decide to CALL a real Python function
you provide, get its actual result back, and use that to build its answer.
This is the foundation of what people call "agents" today.
"""

import os
import sys
import ast
import operator
from datetime import datetime
from time import struct_time

import requests
from anthropic import Anthropic

MODEL = "claude-sonnet-5"
MAX_TOKENS =  1024

SYSTEM_PROMPT = (
    "You are a helpful asistant. Use the available tools whenever they would give you real,"
    " acurate information instead of guessing. "
)

# --- Step 1: define the actual Python function ("tools") ---

def get_current_time() -> str:
    #Tool without parameters. Returns the date.
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#Only these operators are allowed in the calculator, so we never accidentally execute arbitrary code via eval()
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

def _safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsopported expression")

def calculate(expression: str) -> str:
    #A tool with a  parameter. Safely evaluates a basic math expression.
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return str(result)
    except Exception as ex:
        return f"Error evaluating expression: {ex}"

def get_weather(city: str) -> str:
    #A tool that calls a real external API (no key needed, wttr.in).
    try:
        response = requests.get(f"https://wttr.in/{city}?format=%C+%t", timeout=5)
        response.raise_for_status()
        return response.text.strip()
    except Exception as ex:
        return f"Error fetching weather: {ex}"

# --- Step 2: describe those functions to Claude (the tool schema)
# This is JSON schema: it tells Clude the tool's name, what is does, and
# what parameters it expects. Claude uses this description to decide WHEN
# and HOW to call each tool -- it never sees your actual Python code.

TOOLS = [
    {
        "name" : "get_current_time",
        "description" : "Get the current date and time.",
        "input_schema" : {"type" : "object", "properties" : {}},
    },
    {
        "name" : "calculate",
        "description" : "Evaluate a basic math expression (+, -, *, /, **)",
        "input_schema" : {
            "type" : "object",
            "properties" : {
                "expression" : {
                    "type" : "string",
                    "description" : "Math expression e.g. '12 * (3+4)",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name" : "get_weather",
        "description" : "Get the current weather for a city.",
        "input_schema" : {
            "type" : "object",
            "properties" : {
                "city" : {"type" : "string", "description" : "City name, e.g. 'Burgos'"},
            },
            "required": ["city"],
        },
    },
]

#Maps tool name -> actual Python function to run when Claude request it
TOOL_FUNCTIONS = {
    "get_current_time": lambda **kwargs: get_current_time(),
    "calculate": lambda **kwargs: calculate(kwargs["expression"]),
    "get_weather": lambda **kwargs: get_weather(kwargs["city"]),
}

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Please set environment variable 'ANTHROPIC_API_KEY'")
        sys.exit(1)

    client = Anthropic()
    history = []

    print("🤖 Ready. Try asking about the time, a calculation, or the weather somewhere.")
    print("Type 'exit' to quit. \n")

    while True:
        try:
            user_message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("See you!!")
            break

        if user_message.lower() == "exit":
            print("See you!!")
            break

        if not user_message:
            continue

        history.append({"role": "user", "content": user_message})

        #This loop is the core for this project: Claude might need MULTIPLE
        # round-trips before giving a final text answer -- one per tool
        # it decides to call. We keep looping until it stops asking
        # for tools and gives a plain text response.

        while True:
            response = client.messages.create(
                model = MODEL,
                max_tokens= MAX_TOKENS,
                system = SYSTEM_PROMPT,
                tools = TOOLS,
                messages = history,
            )

            history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                #No more tools needed, this is the final answer.
                for block in response.content:
                    if block.type == "text":
                        print(f"Claude: {block.text}\n")
                break

            #response.stop_reason == "tool_use": Claude wants to call one or more
            # tools before continuing. We execute each one for real, and collect the result.
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    print(f"🔧 Claude is calling: {tool_name}({tool_input})")

                    function_to_run = TOOL_FUNCTIONS[tool_name]
                    result = function_to_run(**tool_input)

                    tool_results.append({
                        "type" : "tool_result",
                        "tool_use_id" : block.id,
                        "content" : str(result),
                    })

            # We send the tool results back as a "user" message. Claude will read
            # them and either call another tool or, more likely, give the final text answer.
            history.append({"role": "user", "content": tool_results})

if __name__ == "__main__":
    main()

