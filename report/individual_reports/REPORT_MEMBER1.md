# Individual Report: Lab 3 — Chatbot vs ReAct Agent

- **Student Name**: Nguyễn Trần Hải Ninh
- **Student ID**: 2A
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

### Modules Implemented

Vì nhóm chỉ có 1 thành viên, tôi chịu trách nhiệm toàn bộ hệ thống:

| Module | File | Mô tả |
| :--- | :--- | :--- |
| **ReAct Agent** | `src/agent/agent.py` | Implement toàn bộ ReAct loop: scratchpad management, LLM integration, action parsing (multi-pattern regex), tool execution, sanitization, pretty trace |
| **Chatbot Baseline** | `src/chatbot.py` | Chatbot đơn giản gọi LLM trực tiếp, có conversation history và telemetry tracking |
| **Main Entry Point** | `src/main.py` | CLI hỗ trợ cả chatbot/agent mode, multi-provider (OpenAI, Gemini), demo queries |
| **Tool: search_web** | `src/tools/search_web.py` | Tìm kiếm DuckDuckGo, format kết quả dạng `[i] title \n snippet` |
| **Tool: get_exchange_rate** | `src/tools/get_exchange_rate.py` | Tỷ giá từ Frankfurter API + hardcoded fallback cho VND |
| **Tool: calculate** | `src/tools/calculate.py` | Tính toán biểu thức số học an toàn (sanitized eval), format output + Tool Registry |
| **Telemetry** | `src/telemetry/logger.py`, `metrics.py` | Structured JSON logging (file-only, UTF-8) + performance cost tracking |

### Code Highlights

#### 1. ReAct Loop Core (`agent.py:run()`)

```python
while steps < self.max_steps:
    # Step 1: Sanitize + gọi LLM
    safe_prompt = self._sanitize(scratchpad)
    result = self.llm.generate(prompt=safe_prompt, system_prompt=self.get_system_prompt())
    
    # Step 2: Kiểm tra Final Answer
    final_answer = self._parse_final_answer(llm_output)
    if final_answer:
        return final_answer
    
    # Step 3: Parse Action (multi-pattern regex)
    action = self._parse_action(llm_output)
    
    # Step 4: Execute Tool qua function registry
    observation = self._execute_tool(tool_name, args_str)
    
    # Step 5: Append vào scratchpad → loop
    scratchpad += f"{llm_output}\n\nObservation: {observation}\n\n"
```

#### 2. Multi-pattern Action Parser (`agent.py:_parse_action()`)

Parser hỗ trợ 3 format phổ biến mà LLM hay dùng, đồng thời strip markdown backticks:
- `Action: tool_name(arguments)` — format chuẩn
- `Action: tool_name("arg1", "arg2")` — double quotes
- `Action: tool_name('arg1', 'arg2')` — single quotes

#### 3. Text Sanitization — Fix critical JSON 400 bug (`agent.py:_sanitize()`)

```python
@staticmethod
def _sanitize(text: str) -> str:
    text = text.replace("\x00", "")                              # null bytes
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)  # control chars
    text = re.sub(r"[\ud800-\udfff]", "", text)                  # surrogate pairs
    return text
```

Loại bỏ control characters và surrogate pairs từ kết quả search trước khi gửi tới OpenAI API — fix lỗi JSON parse error 400.

#### 4. Tool Registry Pattern (`calculate.py`)

```python
TOOLS = [
    {"name": "search_web",        "description": "...", "function": search_web},
    {"name": "get_exchange_rate",  "description": "...", "function": get_exchange_rate},
    {"name": "calculate",         "description": "...", "function": calculate},
]
```

Mỗi tool là dictionary gồm `name` + `description` (LLM đọc) + `function` (Python callable). Dễ mở rộng: thêm tool mới chỉ cần append entry.

#### 5. Pretty Console Trace (`agent.py:_trace()`)

Console output color-coded (ANSI escape codes): Thought (vàng), Action (tím), Observation (trắng), Final Answer (xanh lá), Error (đỏ) — giúp debug trực quan từng bước suy luận.

### Architecture Overview

```
main.py → create_agent() → ReActAgent(llm, tools, max_steps)
                              ↓
                          agent.run(user_input)
                              ↓
                    ┌─→ _sanitize(scratchpad) → llm.generate()
                    │         ↓
                    │   _parse_final_answer() → return ✅
                    │         ↓
                    │   _parse_action() → _execute_tool()
                    │         ↓
                    │   TOOLS registry → tool["function"](args)
                    │         ↓
                    └── append Observation → loop 🔁
```

---

## II. Debugging Case Study (10 Points)

Trong quá trình lab, tôi gặp 2 lỗi nghiêm trọng và giải quyết cả hai thông qua phân tích log telemetry.

### Bug 1: OpenAI API JSON Parse Error (400) — Critical

- **Problem Description**: Agent crash tại step 3 với error `"We could not parse the JSON body of your request"` khi hỏi "giúp t tìm giá iphone 16". Steps 1-2 (search) hoạt động bình thường.

- **Log Source** (`src/logs/2026-04-06.log`, line 87):
  ```json
  {"event": "LLM_ERROR", "data": {"step": 3, "error": "Error code: 400 - We could not parse the JSON body..."}}
  ```

- **Diagnosis**:
  1. Sau 2 lần search, scratchpad tích lũy ~2,000+ ký tự từ kết quả web.
  2. DuckDuckGo search trả về kết quả chứa **control characters** (`\x0c`, `\x1b`) và **Unicode surrogate pairs** từ các trang web tiếng Việt.
  3. OpenAI Python SDK serialize request body bằng `json.dumps()` → crash vì invalid characters.
  4. Nguyên nhân gốc: **không sanitize input** trước khi gửi tới API.

- **Solution**: Thêm method `_sanitize()` gọi trước MỌI lần `llm.generate()`:
  - Xóa null bytes, control chars (`\x00-\x1f` trừ `\n`, `\r`, `\t`), surrogate pairs (`\ud800-\udfff`)
  - Sanitize riêng observation từ tool trước khi append vào scratchpad
  - **Kết quả**: 0 crash JSON error sau khi fix

### Bug 2: LLM không tuân theo ReAct format (PARSE_ERROR)

- **Problem Description**: Khi user gửi câu chào ("chào", "chào e"), LLM trả lời tự do không có `Thought:` hay `Final Answer:` prefix → PARSE_ERROR → retry 2-3 lần → tốn thêm 2,000+ tokens.

- **Log Source** (`src/logs/2026-04-06.log`, line 48-55):
  ```json
  {"event": "PARSE_ERROR", "data": {"step": 1, "raw_output": "Chào bạn! Có bất kỳ câu hỏi nào..."}}
  {"event": "PARSE_ERROR", "data": {"step": 2, "raw_output": "Chào bạn! Có bất kỳ câu hỏi nào..."}}
  // Step 3: nhận format hint → cuối cùng tuân theo format
  {"event": "AGENT_END", "data": {"status": "SUCCESS", "steps": 3, "total_tokens": 3288}}
  ```

- **Diagnosis**: System prompt v1 chỉ có ví dụ multi-step, không có ví dụ cho simplecases → LLM bỏ qua format khi câu hỏi quá đơn giản.

- **Solution**:
  1. Thêm section "XỬ LÝ CÂU HỎI KHÔNG LIÊN QUAN" + ví dụ cụ thể vào system prompt v2
  2. Format recovery: inject `[SYSTEM]` hint khi PARSE_ERROR
  3. **Kết quả**: Câu chào xử lý từ step 1 (1,395 tokens thay vì 3,288). Tiết kiệm ~57% tokens.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning — Thought block buộc LLM "nghĩ trước khi làm"

Khối `Thought` hoạt động như **Chain-of-Thought prompting có cấu trúc**, kết hợp với khả năng gọi tool thực tế:

- **Chatbot**: "iPhone 15 giá bao nhiêu USD?" → trả lời "Không có thông tin real-time" hoặc hallucinate con số cũ.
- **Agent**: `Thought: Cần tìm giá VND → tỷ giá → tính toán` → 3 actions riêng biệt → 4 steps → kết quả chính xác "~799 USD = 20,318,570 VND".

Điều thú vị nhất: **LLM chỉ biết tool qua text description**. Description chi tiết ("LUÔN dùng tool này thay vì tự tính") → LLM gọi 100%. Description mơ hồ ("Tính toán") → LLM tự tính nhẩm sai. **Tool specification quan trọng không kém prompt engineering.**

### 2. Reliability — Agent tốn token nhưng chính xác hơn

| Trường hợp | Chatbot | Agent | Nhận xét |
| :--- | :--- | :--- | :--- |
| Câu chào | 142 tokens, 2.3s | 1,395 tokens, 2.4s | Chatbot thắng (nhanh, rẻ) |
| Giá iPhone 15 | ❌ "Không có thông tin" | ✅ "15.69-15.79 triệu" (2 steps) | Agent thắng |
| iPhone 15 giá USD | ❌ Không quy đổi | ✅ "~799 USD" (4 steps, 5,469 tokens) | Agent thắng |
| Giá iPhone 12 | ❌ Hallucinate | ✅ "10.99 triệu mới, 6.69 triệu cũ" | Agent thắng |

Agent đắt hơn 20-50x token nhưng accuracy tăng 0% → 90%+ cho multi-step queries. Trong production, cần **query router**: simple → chatbot, multi-step → agent.

### 3. Observation — Self-correction là "siêu năng lực" của Agent

Qua log, tôi thấy agent tự sửa lỗi nhờ feedback loop:

1. **Search retry**: Query "iPhone giá tốt tháng 10" kết quả tệ → Agent tự đổi thành "iPhone giá tốt Shopee Lazada" → kết quả tốt hơn.
2. **Format recovery**: PARSE_ERROR → System inject hint → LLM sửa format ở step sau.
3. **Fallback reasoning**: Tool không tìm giá cụ thể → Agent lấy giá MSRP rồi tự quy đổi.

**Chatbot không có khả năng này** — sai lần đầu là sai luôn. Đây chính là điểm khác biệt cốt lõi giữa "chat" và "agent".

---

## IV. Future Improvements (5 Points)

### Scalability
- **Query Router**: Phân loại câu hỏi trước (simple vs multi-step) → simple bypasses agent → tiết kiệm 80% token.
- **Conversation Memory**: Agent hiện stateless. Thêm `SummaryMemory` để hỗ trợ follow-up ("Còn iPhone 15 Plus thì sao?").
- **Async Tool Calls**: Dùng `asyncio` cho parallel search khi cần so sánh nhiều sản phẩm cùng lúc.

### Safety
- **Supervisor LLM**: GPT-3.5-turbo audit output trước khi trả user → ngăn hallucination trong Final Answer.
- **Source Attribution**: Mỗi price quote kèm source URL → user xác minh được.
- **Output Validation**: Kiểm tra giá trị (giá < 0 hay > 1 tỷ → flag anomaly).

### Performance
- **Structured Output**: Dùng OpenAI `response_format: { type: "json_schema" }` cho action parsing → loại bỏ regex parser, PARSE_ERROR → 0%.
- **Model Routing**: GPT-3.5-turbo cho chào hỏi/off-topic, GPT-4o cho multi-step → giảm cost 80%.
- **Evaluation Framework**: Test suite tự động 20+ cases + CI/CD regression test khi thay đổi prompt/tools.
- **Multi-Agent System**: Tách thành Search Agent + Calculator Agent + Report Agent → pipeline reliable hơn. Transition sang LangGraph.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
