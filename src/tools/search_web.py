import re
import httpx
from ddgs import DDGS
from typing import Any
 
 
# ─────────────────────────────────────────────
# Tool 1: search_web
# ─────────────────────────────────────────────
 
def search_web(query: str, max_results: int = 5) -> str:
    """
    Tìm kiếm thông tin trên DuckDuckGo.
 
    Args:
        query: Câu truy vấn tìm kiếm (tiếng Việt hoặc tiếng Anh đều được)
        max_results: Số kết quả tối đa trả về (mặc định 5)
 
    Returns:
        Chuỗi text gồm các kết quả tìm kiếm, mỗi kết quả có title + snippet.
        Trả về thông báo lỗi nếu không tìm được gì.
 
    Example:
        search_web("iPhone 16 Pro giá rẻ nhất Việt Nam 2025")
        -> "[1] FPT Shop - iPhone 16 Pro 256GB: 28.990.000đ\n[2] ..."
    """
    try:
        results = []
        with DDGS() as ddgs:
            hits = ddgs.text(query, max_results=max_results)
            for i, hit in enumerate(hits, 1):
                title = hit.get("title", "").strip()
                body = hit.get("body", "").strip()
                results.append(f"[{i}] {title}\n    {body}")
 
        if not results:
            return "Không tìm thấy kết quả nào cho truy vấn này."
 
        return "\n\n".join(results)
 
    except Exception as e:
        return f"Lỗi khi tìm kiếm: {str(e)}"
    

if __name__ == "__main__":
    print("=== Test search_web ===")
    print(search_web("iPhone 16 Pro giá Việt Nam 2025", max_results=3))
