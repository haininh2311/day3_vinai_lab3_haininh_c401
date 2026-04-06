"""
ReAct Agent v1 — Smart Shopper Edition
========================================
Agent sử dụng vòng lặp Thought → Action → Observation để giải quyết
các bài toán multi-step: tìm giá sản phẩm, quy đổi tỷ giá, tính tổng chi phí.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker




class ReActAgent:
    """
    ReAct Agent: Thought → Action → Observation loop.
    Tự động gọi tools (search_web, get_exchange_rate, calculate)
    để trả lời câu hỏi multi-step về mua sắm, giá cả.
    """

    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5, verbose: bool = True):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.verbose = verbose
        self.history: list[str] = []

    # ─────────────────────────────────────────────
    # Pretty console trace
    # ─────────────────────────────────────────────

    def _trace(self, label: str, content: str, indent: bool = False) -> None:
        """In trace đẹp ra console nếu verbose=True."""
        if not self.verbose:
            return

        COLORS = {
            "STEP":        "\033[1;36m",   # cyan bold
            "THOUGHT":     "\033[1;33m",   # yellow bold
            "ACTION":      "\033[1;35m",   # magenta bold
            "OBSERVATION": "\033[0;37m",   # white
            "ANSWER":      "\033[1;32m",   # green bold
            "ERROR":       "\033[1;31m",   # red bold
            "INFO":        "\033[0;90m",   # gray
        }
        RESET = "\033[0m"

        color = COLORS.get(label, "")
        prefix = "    " if indent else ""
        # Hiển thị nội dung, giới hạn hiển thị console 500 chars
        display = content if len(content) <= 500 else content[:500] + "..."
        print(f"{prefix}{color}[{label}]{RESET} {display}")

    # ─────────────────────────────────────────────
    # Text sanitization
    # ─────────────────────────────────────────────

    @staticmethod
    def _sanitize(text: str) -> str:
        """
        Loại bỏ các ký tự gây lỗi JSON khi gửi tới OpenAI API:
        - Control characters (\x00-\x1f) trừ \n, \r, \t
        - Surrogate pairs
        - Null bytes
        """
        # Xóa null bytes
        text = text.replace("\x00", "")
        # Xóa control chars trừ newline, carriage return, tab
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Xóa surrogate pairs (gây lỗi JSON encode)
        text = re.sub(r"[\ud800-\udfff]", "", text)
        return text

    # ─────────────────────────────────────────────
    # System Prompt
    # ─────────────────────────────────────────────

    def get_system_prompt(self) -> str:
        """
        System prompt hướng dẫn LLM tuân theo format ReAct.
        Bao gồm: danh sách tools, format Thought/Action/Observation,
        và ví dụ cụ thể cho bài toán Smart Shopper.
        """
        tool_descriptions = "\n".join(
            [f"  - {t['name']}: {t['description']}" for t in self.tools]
        )

        return f"""Bạn là Smart Shopper Agent — trợ lý mua sắm thông minh.
Bạn giúp người dùng tìm giá tốt nhất, so sánh sản phẩm, quy đổi tiền tệ, và tính toán chi phí.

BẠN CÓ CÁC TOOLS SAU:
{tool_descriptions}

═══════════════════════════════════════
QUY TẮC FORMAT (BẮT BUỘC TUÂN THEO):
═══════════════════════════════════════

Mỗi bước suy luận PHẢI có đúng format sau:

Thought: <phân tích ngắn gọn bước tiếp theo cần làm>
Action: <tên_tool>(<đối_số>)

Hệ thống sẽ trả về kết quả dạng:
Observation: <kết quả từ tool>

Khi ĐÃ CÓ ĐỦ thông tin, kết thúc bằng:
Thought: Tôi đã có đủ thông tin để đưa ra câu trả lời hoàn chỉnh.
Final Answer: <câu trả lời đầy đủ, chi tiết, có số liệu cụ thể>

═══════════════════════════════════════
QUY TẮC QUAN TRỌNG:
═══════════════════════════════════════
1. MỖI lượt CHỈ gọi ĐÚNG MỘT Action. KHÔNG gọi nhiều tool cùng lúc.
2. LUÔN dùng tool calculate() cho phép tính, TUYỆT ĐỐI KHÔNG tự tính trong đầu.
3. LUÔN dùng search_web() khi cần thông tin giá cả, sản phẩm.
4. LUÔN dùng get_exchange_rate() khi cần quy đổi tiền tệ.
5. Argument phải là giá trị CỤ THỂ, không dùng biến hay placeholder.
6. Final Answer phải HOÀN CHỈNH, gồm đầy đủ số liệu đã thu thập, không được cắt ngắn.

═══════════════════════════════════════
XỬ LÝ CÂU HỎI KHÔNG LIÊN QUAN:
═══════════════════════════════════════
Bạn CHỈ hỗ trợ các chủ đề liên quan đến MUA SẮM, GIÁ CẢ, SO SÁNH SẢN PHẨM, QUY ĐỔI TIỀN TỆ, và TÍNH TOÁN CHI PHÍ.

Nếu câu hỏi KHÔNG liên quan (ví dụ: hỏi về thời tiết, lịch sử, lập trình, sức khỏe, chính trị, v.v.), 
hãy trả lời ngay bằng Final Answer mà KHÔNG gọi bất kỳ tool nào:

Thought: Câu hỏi này không liên quan đến mua sắm hay so sánh giá cả. Tôi sẽ từ chối lịch sự.
Final Answer: Xin lỗi, tôi là Smart Shopper Agent — trợ lý chuyên về mua sắm và so sánh giá. Tôi chỉ có thể giúp bạn tìm giá sản phẩm, so sánh giá, quy đổi tiền tệ, và tính toán chi phí mua sắm. Hãy hỏi tôi về sản phẩm bạn muốn mua nhé!

═══════════════════════════════════════
VÍ DỤ HOÀN CHỈNH:
═══════════════════════════════════════

Question: iPhone 16 Pro giá bao nhiêu tiền USD?

Thought: Tôi cần tìm giá iPhone 16 Pro tại Việt Nam trước.
Action: search_web(iPhone 16 Pro gia Viet Nam 2025)

Observation: [1] FPT Shop - iPhone 16 Pro 256GB: 28.990.000đ ...

Thought: Giá khoảng 28,990,000 VND. Bây giờ cần tỷ giá USD/VND để quy đổi.
Action: get_exchange_rate(USD, VND)

Observation: 1 USD = 25,430 VND (tỷ giá tham khảo)

Thought: Cần tính 28990000 / 25430 để ra giá USD.
Action: calculate(28990000 / 25430)

Observation: 1,140.07

Thought: Tôi đã có đủ thông tin để đưa ra câu trả lời hoàn chỉnh.
Final Answer: iPhone 16 Pro 256GB có giá khoảng 28.990.000 VND tại các cửa hàng ở Việt Nam (ví dụ FPT Shop). Quy đổi sang USD theo tỷ giá 1 USD = 25.430 VND, giá tương đương khoảng 1.140,07 USD.

═══════════════════════════════════════
VÍ DỤ TỪ CHỐI CÂU HỎI KHÔNG LIÊN QUAN:
═══════════════════════════════════════

Question: Thủ đô của Việt Nam là gì?

Thought: Câu hỏi này về địa lý, không liên quan đến mua sắm hay so sánh giá. Tôi sẽ từ chối lịch sự.
Final Answer: Xin lỗi, tôi là Smart Shopper Agent — trợ lý chuyên về mua sắm và so sánh giá. Tôi chỉ có thể giúp bạn tìm giá sản phẩm, so sánh giá, quy đổi tiền tệ, và tính toán chi phí mua sắm. Hãy hỏi tôi về sản phẩm bạn muốn mua nhé!"""

    # ─────────────────────────────────────────────
    # Parsers
    # ─────────────────────────────────────────────

    def _parse_action(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Trích xuất tool_name và arguments từ output LLM.
        Hỗ trợ nhiều format phổ biến mà LLM hay dùng.

        Returns:
            (tool_name, args_string) hoặc None nếu không tìm thấy Action.
        """
        # Xóa markdown code blocks nếu LLM wrap trong ```
        cleaned = re.sub(r"```\w*\n?", "", text)

        # Pattern chính: Action: tool_name(arguments)
        # Dùng DOTALL để hỗ trợ args nhiều dòng, nhưng ưu tiên match ngắn nhất
        pattern = r"Action:\s*(\w+)\((.+?)\)\s*$"
        match = re.search(pattern, cleaned, re.MULTILINE)
        if match:
            tool_name = match.group(1).strip()
            args_str = match.group(2).strip().strip("'\"")
            return tool_name, args_str

        # Fallback: Action: tool_name("arg1", "arg2")
        pattern2 = r'Action:\s*(\w+)\(\s*"([^"]+)"\s*(?:,\s*"([^"]+)")?\s*\)'
        match2 = re.search(pattern2, cleaned, re.MULTILINE)
        if match2:
            tool_name = match2.group(1).strip()
            if match2.group(3):
                args_str = f"{match2.group(2)}, {match2.group(3)}"
            else:
                args_str = match2.group(2)
            return tool_name, args_str

        # Fallback: Action: tool_name('arg1', 'arg2')
        pattern3 = r"Action:\s*(\w+)\(\s*'([^']+)'\s*(?:,\s*'([^']+)')?\s*\)"
        match3 = re.search(pattern3, cleaned, re.MULTILINE)
        if match3:
            tool_name = match3.group(1).strip()
            if match3.group(3):
                args_str = f"{match3.group(2)}, {match3.group(3)}"
            else:
                args_str = match3.group(2)
            return tool_name, args_str

        return None

    def _parse_final_answer(self, text: str) -> Optional[str]:
        """
        Trích xuất Final Answer từ output LLM.
        Lấy TOÀN BỘ nội dung sau "Final Answer:" cho đến hết text.

        Returns:
            Nội dung Final Answer hoặc None nếu không có.
        """
        # Tìm "Final Answer:" và lấy mọi thứ sau đó
        pattern = r"Final Answer:\s*(.+)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            answer = match.group(1).strip()
            # Xóa trailing whitespace nhưng giữ nguyên nội dung
            return answer if answer else None
        return None

    # ─────────────────────────────────────────────
    # Tool Execution
    # ─────────────────────────────────────────────

    def _execute_tool(self, tool_name: str, args_str: str) -> str:
        """
        Thực thi tool dựa trên tên và arguments.

        Args:
            tool_name: Tên tool
            args_str: Chuỗi arguments (đã clean quotes)

        Returns:
            Kết quả từ tool hoặc thông báo lỗi.
        """
        # Tìm tool trong registry
        tool_entry = None
        for tool in self.tools:
            if tool["name"] == tool_name:
                tool_entry = tool
                break

        if tool_entry is None:
            logger.log_event("TOOL_ERROR", {
                "error": "HALLUCINATED_TOOL",
                "tool_name": tool_name,
            })
            available = ", ".join(t["name"] for t in self.tools)
            return f"Error: Tool '{tool_name}' không tồn tại. Các tool hợp lệ: {available}"

        func = tool_entry["function"]

        try:
            if tool_name == "calculate":
                # calculate("expression") — 1 arg
                result = func(args_str.strip().strip("'\""))

            elif tool_name == "get_exchange_rate":
                # get_exchange_rate(from, to) — 2 args phân tách bởi dấu phẩy
                parts = [p.strip().strip("'\"") for p in args_str.split(",")]
                if len(parts) >= 2:
                    result = func(parts[0], parts[1])
                else:
                    return f"Error: get_exchange_rate cần 2 arguments (from, to), nhận được: '{args_str}'"

            elif tool_name == "search_web":
                # search_web("query") — 1 arg
                result = func(args_str.strip().strip("'\""))

            else:
                # Generic fallback
                result = func(args_str.strip().strip("'\""))

            logger.log_event("TOOL_RESULT", {
                "tool": tool_name,
                "args": args_str,
                "result_preview": str(result)[:300],
            })
            return str(result)

        except Exception as e:
            logger.log_event("TOOL_ERROR", {
                "error": "EXECUTION_ERROR",
                "tool_name": tool_name,
                "args": args_str,
                "exception": str(e),
            })
            return f"Error khi chay {tool_name}: {str(e)}"

    # ─────────────────────────────────────────────
    # ReAct Loop (core logic)
    # ─────────────────────────────────────────────

    def run(self, user_input: str) -> str:
        """
        Vòng lặp ReAct chính:
        1. Gửi prompt tới LLM → nhận Thought + Action
        2. Parse Action → gọi Tool → nhận Observation
        3. Append Observation vào scratchpad → lặp lại
        4. Khi LLM trả Final Answer → kết thúc

        Args:
            user_input: Câu hỏi từ người dùng

        Returns:
            Final Answer hoặc thông báo lỗi/timeout
        """
        logger.log_event("AGENT_START", {
            "input": user_input,
            "model": self.llm.model_name,
            "max_steps": self.max_steps,
        })

        if self.verbose:
            print()
            print("\033[1;36m" + "=" * 60 + "\033[0m")
            print("\033[1;36m  SMART SHOPPER AGENT — ReAct Trace\033[0m")
            print("\033[1;36m" + "=" * 60 + "\033[0m")
            self._trace("INFO", f"Model: {self.llm.model_name} | Max steps: {self.max_steps}")
            self._trace("INFO", f"Question: {user_input}")
            print("\033[0;90m" + "-" * 60 + "\033[0m")

        # Scratchpad: lưu toàn bộ chuỗi suy luận
        scratchpad = f"Question: {user_input}\n\n"

        steps = 0
        total_tokens = 0
        total_latency_ms = 0

        while steps < self.max_steps:
            steps += 1

            # ── Step 1: Gọi LLM (sanitize trước khi gửi) ──
            safe_prompt = self._sanitize(scratchpad)
            try:
                result = self.llm.generate(
                    prompt=safe_prompt,
                    system_prompt=self.get_system_prompt(),
                )
            except Exception as e:
                logger.log_event("LLM_ERROR", {"step": steps, "error": str(e)})
                return f"Lỗi khi gọi LLM ở bước {steps}: {str(e)}"

            llm_output = result["content"].strip()
            usage = result.get("usage", {})
            latency_ms = result.get("latency_ms", 0)
            total_tokens += usage.get("total_tokens", 0)
            total_latency_ms += latency_ms

            # Track metrics
            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=usage,
                latency_ms=latency_ms,
            )

            logger.log_event("AGENT_STEP", {
                "step": steps,
                "llm_output": llm_output[:500],
                "tokens": usage.get("total_tokens", 0),
                "latency_ms": latency_ms,
            })

            # ── Pretty print: hiển thị step header ──
            if self.verbose:
                print()
                self._trace("STEP", f"Bước {steps}/{self.max_steps}  ({latency_ms}ms | {usage.get('total_tokens', 0)} tokens)")
                # Trích xuất và hiển thị Thought
                thought_match = re.search(r"Thought:\s*(.+?)(?=\nAction:|\nFinal Answer:|$)", llm_output, re.DOTALL)
                if thought_match:
                    self._trace("THOUGHT", thought_match.group(1).strip(), indent=True)

            # ── Step 2: Kiểm tra Final Answer trước ──
            final_answer = self._parse_final_answer(llm_output)
            if final_answer:
                logger.log_event("AGENT_END", {
                    "status": "SUCCESS",
                    "steps": steps,
                    "total_tokens": total_tokens,
                    "total_latency_ms": total_latency_ms,
                    "answer": final_answer[:500],
                })
                if self.verbose:
                    self._trace("ANSWER", final_answer)
                    print()
                    print("\033[0;90m" + "-" * 60 + "\033[0m")
                    self._trace("INFO", f"Hoàn thành: {steps} bước | {total_tokens} tokens | {total_latency_ms}ms")
                    print("\033[1;36m" + "=" * 60 + "\033[0m")
                    print()
                return final_answer

            # ── Step 3: Parse Action ──
            action = self._parse_action(llm_output)

            if action is None:
                # LLM không output Action hay Final Answer hợp lệ
                logger.log_event("PARSE_ERROR", {
                    "step": steps,
                    "raw_output": llm_output[:300],
                })
                if self.verbose:
                    self._trace("ERROR", "Không parse được Action — yêu cầu LLM thử lại", indent=True)
                # Thêm output + hướng dẫn sửa format vào scratchpad
                scratchpad += f"{llm_output}\n\n"
                scratchpad += (
                    "Observation: [SYSTEM] Không tìm thấy Action hợp lệ trong output của bạn. "
                    "Hãy sử dụng đúng format:\n"
                    "Thought: <suy nghĩ>\n"
                    "Action: <tên_tool>(<đối_số>)\n\n"
                    "Hoặc nếu đã có đủ thông tin:\n"
                    "Thought: Tôi đã có đủ thông tin.\n"
                    "Final Answer: <câu trả lời đầy đủ>\n\n"
                )
                continue

            tool_name, args_str = action

            # ── Step 4: Thực thi Tool ──
            logger.log_event("TOOL_CALL", {
                "step": steps,
                "tool": tool_name,
                "args": args_str,
            })

            raw_observation = self._execute_tool(tool_name, args_str)
            # Sanitize observation trước khi đưa vào scratchpad
            observation = self._sanitize(raw_observation)

            if self.verbose:
                self._trace("ACTION", f"{tool_name}({args_str})", indent=True)
                self._trace("OBSERVATION", observation, indent=True)

            # ── Step 5: Cập nhật scratchpad với format rõ ràng ──
            scratchpad += f"{llm_output}\n\nObservation: {observation}\n\n"

        # ── Timeout: hết max_steps ──
        logger.log_event("AGENT_END", {
            "status": "TIMEOUT",
            "steps": steps,
            "total_tokens": total_tokens,
            "total_latency_ms": total_latency_ms,
        })

        # Thử cho LLM cơ hội cuối để tổng hợp
        scratchpad += (
            "Thought: Tôi đã hết số bước cho phép. "
            "Tôi cần tổng hợp thông tin đã thu thập và đưa ra Final Answer ngay.\n"
            "Final Answer:"
        )
        try:
            final_result = self.llm.generate(
                prompt=self._sanitize(scratchpad),
                system_prompt=self.get_system_prompt(),
            )
            final_text = final_result["content"].strip()
            if final_text:
                return final_text
        except Exception:
            pass

        return (
            f"Agent đã chạy {self.max_steps} bước nhưng không thể kết luận. "
            f"Hãy thử lại với câu hỏi cụ thể hơn."
        )
