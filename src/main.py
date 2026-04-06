"""
Smart Shopper — Main Entry Point
=================================
Chạy cả Chatbot baseline và ReAct Agent.
Dùng: python -m src.main [chatbot|agent] [openai|google]
"""

import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.agent import ReActAgent
from src.chatbot import Chatbot
from src.core.openai_provider import OpenAIProvider
from src.core.gemini_provider import GeminiProvider
from src.tools.calculate import TOOLS


# ─────────────────────────────────────────────
# Factory helpers
# ─────────────────────────────────────────────

def _create_llm(provider: str):
    """Tạo LLM provider từ tên."""
    load_dotenv()

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY in .env")
        model = os.getenv("DEFAULT_MODEL", "gpt-4o")
        return OpenAIProvider(model_name=model, api_key=api_key)

    elif provider == "google":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY in .env")
        model = os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
        return GeminiProvider(model_name=model, api_key=api_key)

    else:
        raise ValueError(f"Provider '{provider}' không được hỗ trợ. Dùng: openai | google")


def create_agent(provider: str = "openai") -> ReActAgent:
    """Tạo ReAct Agent."""
    load_dotenv()
    llm = _create_llm(provider)
    max_steps = int(os.getenv("AGENT_MAX_STEPS", "5"))
    return ReActAgent(llm=llm, tools=TOOLS, max_steps=max_steps)


def create_chatbot(provider: str = "openai") -> Chatbot:
    """Tạo Chatbot baseline."""
    llm = _create_llm(provider)
    return Chatbot(llm=llm)


# ─────────────────────────────────────────────
# Test cases cho Smart Shopper
# ─────────────────────────────────────────────

SAMPLE_QUERIES = [
    "iPhone 16 Pro Max giá bao nhiêu tiền?",
    "So sánh giá Samsung Galaxy S25 Ultra và iPhone 16 Pro Max",
    "Tôi muốn mua iPhone 16 Pro Max, giá bao nhiêu USD?",
    "Tính tổng tiền nếu mua 2 chiếc iPhone 16 Pro Max và được giảm 10%",
]


# ─────────────────────────────────────────────
# Interactive CLI
# ─────────────────────────────────────────────

def run_interactive(mode: str, provider: str) -> None:
    """Chạy interactive CLI cho chatbot hoặc agent."""

    if mode == "chatbot":
        bot = create_chatbot(provider)
        label = "Chatbot"
        print("=" * 60)
        print("  SMART SHOPPER CHATBOT (Baseline — Khong co Tools)")
        print("=" * 60)
    else:
        bot = create_agent(provider)
        label = "Agent"
        print("=" * 60)
        print("  SMART SHOPPER REACT AGENT (Co Tools)")
        print("=" * 60)

    print(f"  Provider: {provider} | Model: {bot.llm.model_name}")
    print(f"  Mode: {mode.upper()}")
    print("-" * 60)
    print("  Gõ 'exit' để thoát | 'demo' để chạy test cases mẫu")
    print("=" * 60 + "\n")

    while True:
        user_input = input("Bạn: ").strip()
        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("Tạm biệt!")
            break

        if user_input.lower() == "demo":
            print("\n--- Chạy demo với các câu hỏi mẫu ---\n")
            for i, query in enumerate(SAMPLE_QUERIES, 1):
                print(f"[Demo {i}] {query}")
                if mode == "chatbot":
                    answer = bot.chat(query)
                else:
                    answer = bot.run(query)
                print(f"{label}: {answer}\n")
                print("-" * 40 + "\n")
            continue

        try:
            if mode == "chatbot":
                answer = bot.chat(user_input)
            else:
                answer = bot.run(user_input)
            print(f"{label}: {answer}\n")
        except KeyboardInterrupt:
            print("\nĐã dừng bởi người dùng.")
            break
        except Exception as e:
            print(f"Lỗi: {e}\n")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main() -> None:
    """
    Usage:
        python -m src.main              → agent + openai (default)
        python -m src.main chatbot      → chatbot + openai
        python -m src.main agent google → agent + google
    """
    load_dotenv()

    mode = sys.argv[1] if len(sys.argv) > 1 else "agent"
    provider = sys.argv[2] if len(sys.argv) > 2 else os.getenv("DEFAULT_PROVIDER", "openai")

    if mode not in {"chatbot", "agent"}:
        print("Usage: python -m src.main [chatbot|agent] [openai|google]")
        sys.exit(1)

    try:
        run_interactive(mode, provider)
    except Exception as e:
        print(f"Khoi tao that bai: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
