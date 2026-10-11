"""A tiny, reusable tool-calling loop for any OpenAI-compatible endpoint
(OpenAI, Together AI, Runpod vLLM, Groq, OpenRouter, ...). Use it or write your own agent."""
import json


def run_tool_agent(client, model, system_prompt, user_input, tools, tool_impls, max_steps=5):
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}]
    calls, t_in, t_out, final = [], 0, 0, ""
    for _ in range(max_steps):
        resp = client.chat.completions.create(model=model, messages=messages, tools=tools)
        if getattr(resp, "usage", None):
            t_in += resp.usage.prompt_tokens or 0
            t_out += resp.usage.completion_tokens or 0
        msg = resp.choices[0].message
        if not msg.tool_calls:
            final = msg.content or ""
            break
        messages.append({
            "role": "assistant", "content": msg.content,
            "tool_calls": [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name,
                                         "arguments": tc.function.arguments}}
                           for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append({"name": tc.function.name, "arguments": args})
            impl = tool_impls.get(tc.function.name)
            result = impl(**args) if impl else {"error": "unknown tool"}
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)})
    return {"output": final, "tool_calls": calls, "tokens_in": t_in, "tokens_out": t_out}
