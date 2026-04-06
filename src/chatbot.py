"""
Chatbot Baseline — Smart Shopper Edition
=========================================
Chatbot đơn giản gọi LLM trực tiếp **không có tools**.
Dùng để so sánh với ReAct Agent và minh chứng hạn chế
của LLM thuần khi gặp các câu hỏi multi-step (giá cả, tỷ giá, tính toán).
"""

import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.llm_provider import LLMProvider
from src.core.openai_provider import OpenAIProvider
from src.core.gemini_provider import GeminiProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


# ─────────────────────────────────────────────
# Chatbot class
# ─────────────────────────────────────────────

class Chatbot:
    """
    Chatbot baseline — chỉ gọi LLM, không dùng tools.
    Mục đích: cho thấy LLM thuần sẽ hallucinate khi cần
    thông tin real-time (giá điện thoại, tỷ giá) hoặc tính toán chính xác.
    """

    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self.conversation_history: list[str] = []

    def get_system_prompt(self) -> str:
        """System prompt cho chatbot — không có tool nào."""
        return (
            "Bạn là Smart Shopper Assistant — trợ lý mua sắm thông minh.\n"
            "Bạn giúp người dùng so sánh giá sản phẩm, tính toán chi phí, "
            "và đưa ra gợi ý mua sắm.\n\n"
            "LƯU Ý: Bạn KHÔNG có quyền truy cập internet hay bất kỳ công cụ nào.\n"
            "Hãy trả lời dựa trên kiến thức sẵn có. "
            "Nếu không chắc chắn về giá cả hoặc thông tin mới nhất, "
            "hãy nói rõ rằng bạn không có dữ liệu real-time.\n\n"
            "Trả lời ngắn gọn, chính xác, bằng tiếng Việt."
        )

    def chat(self, user_input: str) -> str:
        """
        Gửi tin nhắn tới LLM và nhận phản hồi.
        Ghi log telemetry cho mọi request.
        """
        logger.log_event("CHATBOT_REQUEST", {
            "input": user_input,
            "model": self.llm.model_name,
        })

        # Xây prompt với conversation history (giữ 10 lượt gần nhất)
        history_context = ""
        if self.conversation_history:
            history_context = "\n".join(self.conversation_history[-10:]) + "\n\n"

        full_prompt = f"{history_context}User: {user_input}"

        try:
            result = self.llm.generate(
                prompt=full_prompt,
                system_prompt=self.get_system_prompt(),
            )

            content = result["content"]
            usage = result.get("usage", {})
            latency_ms = result.get("latency_ms", 0)

            # Track metrics
            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=usage,
                latency_ms=latency_ms,
            )

            logger.log_event("CHATBOT_RESPONSE", {
                "output": content[:200],  # truncate for log
                "tokens": usage.get("total_tokens", 0),
                "latency_ms": latency_ms,
            })

            # Lưu history
            self.conversation_history.append(f"User: {user_input}")
            self.conversation_history.append(f"Assistant: {content}")

            return content

        except Exception as e:
            logger.error(f"Chatbot error: {e}")
            return f"Xin lỗi, đã xảy ra lỗi: {str(e)}"


# ─────────────────────────────────────────────
# Factory + Interactive CLI
# ─────────────────────────────────────────────

def create_chatbot(provider: str = "openai") -> Chatbot:
    """Tạo chatbot với provider được chỉ định."""
    load_dotenv()

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY in .env")
        model = os.getenv("DEFAULT_MODEL", "gpt-4o")
        llm = OpenAIProvider(model_name=model, api_key=api_key)

    elif provider == "google":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY in .env")
        llm = GeminiProvider(model_name="gemini-1.5-flash", api_key=api_key)

    else:
        raise ValueError(f"Provider '{provider}' không được hỗ trợ cho chatbot.")

    return Chatbot(llm=llm)


def main() -> None:
    """Interactive CLI cho chatbot baseline."""
    load_dotenv()
    provider = os.getenv("DEFAULT_PROVIDER", "openai")

    try:
        chatbot = create_chatbot(provider)
    except Exception as e:
        print(f"Khởi tạo chatbot thất bại: {e}")
        return

    print("=" * 55)
    print("SMART SHOPPER CHATBOT (Baseline — Không có Tools)")
    print("=" * 55)
    print(f"  Provider: {provider} | Model: {chatbot.llm.model_name}")
    print("  Gõ 'exit' hoặc 'quit' để thoát.\n")

    while True:
        user_input = input("Bạn: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Tạm biệt!")
            break

        answer = chatbot.chat(user_input)
        print(f"Chatbot: {answer}\n")


if __name__ == "__main__":
    main()
