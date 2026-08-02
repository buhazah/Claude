#!/usr/bin/env python3
"""Stream a chat completion from an OpenAI-compatible endpoint (e.g. TokenRouter).

Usage:
    export TOKENROUTER_API_KEY=sk-...
    python stream_chat.py "What kind of model are you?"
    python stream_chat.py --model moonshotai/kimi-k3-free "Hello"
"""
import argparse
import os
import sys

from openai import OpenAI

DEFAULT_BASE_URL = "https://api.tokenrouter.com/v1"
DEFAULT_MODEL = "moonshotai/kimi-k3-free"
DEFAULT_SYSTEM_PROMPT = "You are an intelligent assistant, please reply concisely."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?", default="Hello, what kind of model are you?")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--system", default=DEFAULT_SYSTEM_PROMPT)
    return parser.parse_args()


def stream_chat(client: OpenAI, model: str, system: str, prompt: str) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
    )

    content_parts = []
    for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                content_parts.append(delta.content)
                print(delta.content, end="", flush=True)
        if chunk.usage:
            print(
                f"\n\n[usage] prompt={chunk.usage.prompt_tokens} "
                f"completion={chunk.usage.completion_tokens} "
                f"total={chunk.usage.total_tokens}",
                file=sys.stderr,
            )
    print()
    return "".join(content_parts)


def main() -> None:
    args = parse_args()

    api_key = os.environ.get("TOKENROUTER_API_KEY")
    if not api_key:
        sys.exit("Error: set the TOKENROUTER_API_KEY environment variable with your API key.")

    client = OpenAI(base_url=args.base_url, api_key=api_key)
    stream_chat(client, args.model, args.system, args.prompt)


if __name__ == "__main__":
    main()
