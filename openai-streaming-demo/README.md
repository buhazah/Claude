# OpenAI-Compatible Streaming Demo

Minimal script that streams a chat completion from TokenRouter's
OpenAI-compatible API (`https://api.tokenrouter.com/v1`) using the official
`openai` Python SDK.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your key
export TOKENROUTER_API_KEY=sk-your-key-here
```

## Usage

```bash
python stream_chat.py "What kind of model are you?"
python stream_chat.py --model moonshotai/kimi-k3-free "Hello"
```

Response tokens print as they arrive; token usage (from
`stream_options={"include_usage": True}`) is printed to stderr once the
stream finishes.
