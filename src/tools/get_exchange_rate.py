import re
from urllib import response
import httpx
import httpx

def get_exchange_rate(from_currency: str, to_currency: str) -> str:
    """
    Lấy tỷ giá giữa 2 loại tiền tệ.

    - Dùng Frankfurter API cho các currency chuẩn (USD, EUR, JPY…)
    - Fallback cho VND (do ECB không hỗ trợ)

    Returns:
        Chuỗi mô tả tỷ giá hoặc lỗi rõ ràng
    """

    VND_RATES = {
        "USD": 25430,
        "EUR": 27800,
        "JPY": 165,
        "GBP": 32100,
    }

    from_cur = from_currency.upper()
    to_cur = to_currency.upper()

    # ===== Handle VND =====
    if from_cur == "VND" and to_cur in VND_RATES:
        rate = 1 / VND_RATES[to_cur]
        return f"1 VND = {rate:.8f} {to_cur} (tỷ giá tham khảo)"

    if to_cur == "VND" and from_cur in VND_RATES:
        rate = VND_RATES[from_cur]
        return f"1 {from_cur} = {rate:,} VND (tỷ giá tham khảo)"

    # ===== Call API =====
    try:
        url = "https://api.frankfurter.app/latest"

        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            response = client.get(
                url,
                params={
                    "from": from_cur,
                    "to": to_cur
                }
            )
            response.raise_for_status()

        data = response.json()

        # Validate response
        if "rates" not in data or to_cur not in data["rates"]:
            return f"Không hỗ trợ cặp tiền {from_cur}/{to_cur}"

        rate = data["rates"][to_cur]
        date = data.get("date", "N/A")

        return f"1 {from_cur} = {rate} {to_cur} (cập nhật: {date})"

    except httpx.HTTPStatusError as e:
        return f"Lỗi HTTP: {e.response.status_code}"

    except httpx.RequestError:
        return "Lỗi kết nối tới server tỷ giá"

    except Exception as e:
        return f"Lỗi không xác định: {str(e)}"

if __name__ == "__main__":

 
    print("\n=== Test get_exchange_rate ===")
    print(get_exchange_rate("USD", "VND"))
    print(get_exchange_rate("USD", "JPY"))
