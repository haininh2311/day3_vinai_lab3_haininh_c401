import re
from typing import Any
import sys

sys.path.append("../..")  

from src.tools.get_exchange_rate import get_exchange_rate
from src.tools.search_web import search_web

def calculate(expression: str) -> str:
    """
    Tính toán biểu thức số học đơn giản.
    Dùng khi cần cộng, trừ, nhân, chia, phần trăm — tránh để LLM tự tính (dễ sai).
 
    Args:
        expression: Biểu thức toán học dạng chuỗi.
                    Chỉ cho phép số và các phép toán: + - * / ( ) . %
                    VD: "28990000 / 25430", "999 * 25430", "(28990000 - 999*25430) / 25430"
 
    Returns:
        Kết quả tính toán dạng chuỗi, làm tròn 2 chữ số thập phân nếu cần.
        Trả về thông báo lỗi nếu biểu thức không hợp lệ.
 
    Example:
        calculate("28990000 / 25430") -> "1140.23"
        calculate("999 * 25430")      -> "25,404,570"
    """
    # Sanitize: chỉ cho phép ký tự số và toán tử cơ bản
    cleaned = expression.replace(",", "").replace(" ", "")
    if not re.fullmatch(r"[\d\+\-\*\/\(\)\.\%]+", cleaned):
        return f"Biểu thức không hợp lệ: '{expression}'. Chỉ dùng số và phép toán + - * / ( )"
 
    try:
        result = eval(cleaned)  # noqa: S307 — safe vì đã sanitize ký tự
        # Format output: số nguyên lớn thì dùng dấu phẩy, số thập phân thì làm tròn 2
        if isinstance(result, float):
            if result == int(result):
                return f"{int(result):,}"
            return f"{result:,.2f}"
        return f"{result:,}"
    except ZeroDivisionError:
        return "Lỗi: Chia cho 0."
    except Exception as e:
        return f"Lỗi tính toán: {str(e)}"
 
 
# ─────────────────────────────────────────────
# Tool Registry — đăng ký để agent nhận diện
# ─────────────────────────────────────────────
 
TOOLS = [
    {
        "name": "search_web",
        "description": (
            "Tìm kiếm thông tin trên internet dùng DuckDuckGo. "
            "Dùng khi cần tìm giá sản phẩm, thông số kỹ thuật, hoặc bất kỳ thông tin nào cần cập nhật. "
            "Input: câu truy vấn tìm kiếm (string). "
            "Output: danh sách kết quả gồm title và snippet từ các trang web. "
            "Ví dụ: search_web('iPhone 16 Pro giá rẻ nhất Việt Nam 2025')"
        ),
        "function": search_web,
    },
    {
        "name": "get_exchange_rate",
        "description": (
            "Lấy tỷ giá hối đoái hiện tại giữa 2 loại tiền tệ. "
            "Hỗ trợ các cặp: USD, EUR, GBP, JPY, AUD, ... và VND (tỷ giá tham khảo). "
            "Input: from_currency (string), to_currency (string) — mã ISO 4217. "
            "Output: tỷ giá dạng '1 USD = 25430 VND'. "
            "Ví dụ: get_exchange_rate('USD', 'VND')"
        ),
        "function": get_exchange_rate,
    },
    {
        "name": "calculate",
        "description": (
            "Tính toán biểu thức số học: cộng, trừ, nhân, chia. "
            "LUÔN dùng tool này thay vì tự tính trong đầu để tránh sai số. "
            "Input: biểu thức toán học dạng string, chỉ dùng số và + - * / ( ). "
            "Output: kết quả tính toán. "
            "Ví dụ: calculate('28990000 / 25430')"
        ),
        "function": calculate,
    },
]


if __name__ == "__main__":
 
    print("\n=== Test calculate ===")
    print(calculate("28990000 / 25430"))
    print(calculate("999 * 25430"))
    print(calculate("(28990000 - 999 * 25430) / 25430"))