# Tool use chatbot (learning project)

A chatbot that can call real Python functions ("tools") when it needs
actual information instead of guessing — the foundation of what's called
an "agent" today.

## Getting it running

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Make sure `ANTHROPIC_API_KEY`** is set (same as previous projects).

3. **Run:**
   ```bash
   python main.py
   ```

4. Try things like:
   - "What time is it?"
   - "What's 234 * 17 + 9?"
   - "What's the weather in Burgos?"
   - "What's the weather in Tokyo, and what's 100/4?" (this one triggers *two* tool calls)

## New concept vs. previous projects

So far, Claude only ever generated text. Here it can decide: *"I need real
data to answer this properly — let me call a function."* Your code actually
executes that function and feeds the real result back to Claude, which
then writes the final answer grounded in that data.

## How the loop works

1. You send Claude your message + a list of available tools (name,
   description, expected parameters — described as JSON Schema).
2. Claude replies with either:
   - a normal text answer (`stop_reason != "tool_use"`), or
   - a request to call one or more tools (`stop_reason == "tool_use"`).
3. If it requested tools, **your code** runs the real Python function,
   and you send the result back to Claude as a `tool_result`.
4. Claude reads the result and either calls another tool, or gives the
   final text answer. Repeat until you get a final answer.

This project includes 3 example tools:
- `get_current_time` — no parameters, purely local.
- `calculate` — one parameter, local (uses a restricted, safe expression
  evaluator — never plain `eval()`, which would be a security risk).
- `get_weather` — one parameter, calls a real external API (`wttr.in`,
  no API key required).