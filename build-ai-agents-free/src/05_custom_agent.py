# custom agent — built on the free stack from this repo.
# same pattern as agent.py: fallback (groq -> gemini) + tools + memory,
# with two extra hand-written tools (calculator, current time) added on top
# of search. swap the tools/system_prompt for whatever task you need.
# needs GROQ_API_KEY (and optionally GOOGLE_API_KEY) in .env
# run: python3 src/05_custom_agent.py

from datetime import datetime, timezone

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()


# --- fallback: try groq first, fall back to gemini (both free) ---
def get_model():
    try:
        model = ChatGroq(model="llama-3.3-70b-versatile")
        model.invoke("ping")
        print("using groq")
        return model
    except Exception as e:
        print(f"groq failed ({e}); falling back to gemini")
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash")


# --- tools ---
search = DuckDuckGoSearchRun()  # free, no key


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '12 * (3 + 4)'."""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "error: only numbers and + - * / ( ) are allowed"
    return str(eval(expression, {"__builtins__": {}}, {}))


@tool
def current_time() -> str:
    """Get the current UTC date and time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# --- memory: same thread_id = same conversation ---
agent = create_agent(
    model=get_model(),
    tools=[search, calculator, current_time],
    system_prompt=(
        "You are a helpful assistant. Use your tools when they help answer "
        "accurately, and remember the conversation."
    ),
    checkpointer=InMemorySaver(),
)


def main():
    config = {"configurable": {"thread_id": "chat-1"}}

    r1 = agent.invoke(
        {"messages": [{"role": "user", "content": "what's the current time, and what's 17 * 24?"}]},
        config,
    )
    print(r1["messages"][-1].content)

    r2 = agent.invoke(
        {"messages": [{"role": "user", "content": "search for the latest langchain version."}]},
        config,
    )
    print(r2["messages"][-1].content)


if __name__ == "__main__":
    main()
