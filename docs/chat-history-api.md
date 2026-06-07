# Chat 与 History Router 接口文档（中文）

更新时间：2026-04-12  
适用代码：`backend/app/api/v1/endpoints/chat.py`、`backend/app/api/v1/endpoints/history.py`

## 1. 基本约定

- 接口统一前缀：`/api/v1`
- 本文接口完整路径前缀分别为：
  - Chat：`/api/v1/chat`
  - History：`/api/v1/history`
- 鉴权：除登录类接口外，本文所有接口都依赖 `get_current_user_id`，需要携带：
  - `Authorization: Bearer <access_token>`
- 常见错误返回：

```json
{
  "detail": "错误信息"
}
```

---

## 2. Chat Router（`/api/v1/chat`）

### 2.1 创建会话

- 方法：`POST`
- 路径：`/api/v1/chat/create_session`
- 请求参数：无（仅依赖登录态）
- 成功响应（`200`，`SessionResponse`）：

```json
{
  "session_id": "a1b2c3d4e5f67890",
  "status": "success",
  "message": "Session created successfully"
}
```

---

### 2.2 快速解析单文档（写入 Redis）

- 方法：`POST`
- 路径：`/api/v1/chat/quick_parse`
- `Content-Type`：`multipart/form-data`
- Query 参数：
  - `session_id`（必填，字符串）
- Form 参数：
  - `file`（必填，文件）
- 支持格式：`docx`、`pdf`、`txt`
- 限制：
  - 每个 `session_id` 仅允许 1 个快速解析文档
  - `pdf` 最多 4 页
  - `docx/txt` 最多 4000 字符
  - 解析结果默认保留约 2 小时（Redis TTL）

`pdf` 成功响应示例：

```json
{
  "status": "success",
  "message": "文档解析完成",
  "session_id": "sess001",
  "filename": "a.pdf",
  "file_type": "pdf",
  "pages": 3,
  "content_length": 2180,
  "limit_info": "PDF页数限制: 4页",
  "expiry_hours": 2
}
```

`docx/txt` 成功响应示例：

```json
{
  "status": "success",
  "message": "文档解析完成",
  "session_id": "sess001",
  "filename": "a.docx",
  "file_type": "docx",
  "character_count": 1680,
  "content_length": 1680,
  "limit_info": "字符数限制: 4000字符",
  "expiry_hours": 2
}
```

常见失败：
- `400`：格式不支持、重复上传、页数/字符数超限、文件为空
- `401`：未认证
- `500`：Redis/服务内部错误

---

### 2.3 上传多个知识库文件（入 ES + PG）

- 方法：`POST`
- 路径：`/api/v1/chat/upload_files`
- `Content-Type`：`multipart/form-data`
- Query 参数：
  - `session_id`（这个先不填，这里上传的文件可以让）
- Form 参数：
  - `files`（必填，文件数组）

成功（全部成功）示例：

```json
{
  "status": "success",
  "message": "所有文件解析成功",
  "successful_files": ["A.pdf", "B.docx"],
  "total_files": 2
}
```

部分成功示例：

```json
{
  "status": "partial_success",
  "message": "部分文件解析成功，1 个成功，1 个失败",
  "successful_files": ["A.pdf"],
  "failed_files": ["B.xlsx: 文件解析失败 - ..."],
  "total_files": 2
}
```

全部失败时返回 `400`，`detail` 为对象：

```json
{
  "detail": {
    "status": "failed",
    "message": "所有文件解析失败",
    "failed_files": ["A.pdf: 文件内容为空"],
    "total_files": 1
  }
}
```

说明：
- 后端会检查同用户下文件名是否重复，重复则直接 `400`
- `xlsx/xls` 做了文件头校验
- 单文件失败不会影响其他文件继续处理

---

### 2.4 获取快速解析内容

- 方法：`GET`
- 路径：`/api/v1/chat/get_parsed_content`
- Query 参数：
  - `session_id`（必填，字符串）

成功响应：

```json
{
  "status": "success",
  "session_id": "sess001",
  "content": "...解析出的文本...",
  "content_length": 1680,
  "remaining_seconds": 5231
}
```

常见失败：
- `404`：内容不存在或已过期

---

### 2.5 基于文档对话（流式 SSE）

- 方法：`POST`
- 路径：`/api/v1/chat/chat_on_docs`
- Query 参数：
  - `session_id`（必填，字符串）
  - `deep_think`（可选，布尔，默认 `false`）
- Body（JSON，`ChatRequest`）：

```json
{
  "message": "请总结我上传文档的重点"
}
```

响应：
- `StreamingResponse`
- `Content-Type: text/event-stream`
- 流式数据由 `get_chat_completion(...)` 生成（SSE 分片）

说明：
- 当 `deep_think=true` 时，后端选择 `deepseek-reasoner`；否则 `deepseek-chat`
- 若知识库检索失败，接口仍会继续生成回答（无 references）

---

### 2.6 获取会话文档列表

- 方法：`GET`
- 路径：`/api/v1/chat/sessions/{session_id}/documents`
- Path 参数：
  - `session_id`（必填，字符串）
- 响应模型：`SessionDocumentsResponse`

成功响应示例：

```json
{
  "session_id": "sess001",
  "has_documents": true,
  "documents": [
    {
      "id": 1,
      "session_id": "sess001",
      "document_name": "A.pdf",
      "document_type": "pdf",
      "file_size": 34567,
      "upload_time": "2026-04-11T10:21:32",
      "created_at": "2026-04-11T10:21:32",
      "updated_at": "2026-04-11T10:21:32"
    }
  ],
  "total_count": 1
}
```

---

### 2.7 获取会话文档摘要

- 方法：`GET`
- 路径：`/api/v1/chat/sessions/{session_id}/documents/summary`
- Path 参数：
  - `session_id`（必填，字符串）
- 响应模型：`SessionDocumentSummary`

成功响应示例：

```json
{
  "session_id": "sess001",
  "has_documents": true,
  "latest_document_name": "A.pdf",
  "latest_document_type": "pdf",
  "latest_upload_time": "2026-04-11T10:21:32",
  "total_documents": 3
}
```

---

### 2.8 AI 搜索增强对话（流式 SSE）

- 方法：`POST`
- 路径：`/api/v1/chat/ai_search/`
- Query 参数：
  - `session_id`（必填，字符串）
- Body（JSON，`ChatRequest`）：

```json
{
  "message": "请结合学校资料和网络信息回答这个问题"
}
```

响应：
- `StreamingResponse`
- `Content-Type: text/event-stream`
- 流式数据由 `get_chat_completion_with_search(...)` 生成（SSE 分片）

处理逻辑说明：
- 先校验用户是否有知识库（`verify_user_knowledgebase`）
- 若有知识库，执行本地检索（`retrieve_content`）
- 同时执行 Web 搜索（`store_and_query_snippets`）
- 将知识库结果 + Web 搜索结果 + 历史问题拼装到提示词后流式回答

常见失败：
- `401`：未认证
- `461`：当前用户没有知识库（来自 `verify_user_knowledgebase`）
- `500`：检索/模型/服务内部错误

---

### 2.9 Deep Research（Agent 流式 SSE）

- 方法：`POST`
- 路径：`/api/v1/chat/deep_research/`
- Query 参数：
  - `session_id`（必填，字符串）
- Body（JSON，`ChatRequest`）：

```json
{
  "message": "请深入分析这个问题"
}
```

响应：
- `StreamingResponse`
- `Content-Type: text/event-stream`
- 流式数据由 `final_answer(question, user_id)` 生成（SSE 分片）

处理逻辑说明：
- 先由 Agent 规划是否调用“本地文档搜索/网络搜索”
- 本地文档搜索会使用当前登录用户 `user_id` 作为检索索引
- 汇总检索结果后由大模型生成最终回答

鉴权说明：
- 该接口依赖 `get_current_user_id`，必须携带 `Authorization: Bearer <access_token>`
- 缺少或无效 token 会返回 `401 Unauthorized`

---

## 3. History Router（`/api/v1/history`）

### 3.1 获取当前用户文件列表

- 方法：`GET`
- 路径：`/api/v1/history/get_files`
- 请求参数：无（仅依赖登录态）
- 响应模型：`List[FilestResponse]`

成功响应示例：

```json
[
  {
    "user_id": "12210001",
    "file_name": "A.pdf",
    "created_at": "2026-04-11T10:21:32",
    "updated_at": "2026-04-11T10:31:05"
  }
]
```

无数据时返回空数组：`[]`

---

### 3.2 删除用户指定文件

- 方法：`DELETE`
- 路径：`/api/v1/history/delete_file/{file_name}`
- Path 参数：
  - `file_name`（必填，字符串；URL 编码后传入）

成功响应示例：

```json
{
  "message": "文件删除成功"
}
```

常见失败：
- `404`：文件不存在或删除失败
- `401`：未认证

---

### 3.3 按会话获取消息历史

- 方法：`GET`
- 路径：`/api/v1/history/get_messages`
- Query 参数：
  - `session_id`（必填，字符串）

成功响应示例：

```json
[
  {
    "message_id": "3f3bc0d6-2d9e-4e3b-9ce6-98e48f4e0e90",
    "session_id": "sess001",
    "user_question": "请总结第一章",
    "model_answer": "第一章主要讲...",
    "documents": "[...]",
    "recommended_questions": "[...]",
    "think": "...",
    "created_at": "2026-04-11 10:35:12"
  }
]
```

说明：
- `documents`、`recommended_questions` 当前由数据库字段直接返回，可能是字符串化 JSON

---

### 3.4 获取用户所有会话

- 方法：`GET`
- 路径：`/api/v1/history/get_sessions`
- 请求参数：无（仅依赖登录态）
- 响应模型：`SessionListResponse`
- 问完第一个问题后，session name会更新为llm生成的问题总结
成功响应示例：

```json
{
  "user_id": "12210001",
  "sessions": [
    {
      "session_id": "sess001",
      "session_name": "session-sess001",
      "user_id": "12210001",
      "created_at": "2026-04-11 10:20:00",
      "updated_at": "2026-04-11 10:50:00"
    }
  ]
}
```

---

## 4. 前端联调建议

- 对 `chat_on_docs` 使用 `EventSource` 或支持 SSE 的 fetch 流式读取。
- 对 `ai_search` 与 `deep_research` 也使用 SSE 读取，建议区分 `thinking=true/false` 展示不同 UI 区块。
- 调用 `deep_research` 时务必带 `Authorization: Bearer <access_token>`，否则会返回 `401`。
- 对 `upload_files` 的错误处理要兼容两种格式：
  - 字符串型 `detail`
  - 对象型 `detail`（包含 `failed_files`）
- 删除文件接口的 `file_name` 记得先做 URL 编码。
- 若接口返回 `401`，统一走重新登录逻辑并刷新 token。

---

## 5. 前端接入状态更新（2026-04-22）

Assistant 当前按真实 `chat/* + history/*` 接入，不接标准化 `/api/v1/assistant/*` 目标合约。

### 5.1 消息发送映射

- 联网搜索未勾选：
  - `Fast` -> `POST /api/v1/chat/chat_on_docs?deep_think=false`
  - `Thinking` -> `POST /api/v1/chat/chat_on_docs?deep_think=true`
  - `Deep Research` 禁用
- 联网搜索已勾选：
  - `Fast` 禁用
  - `Thinking` -> `POST /api/v1/chat/ai_search/`
  - `Deep Research` -> `POST /api/v1/chat/deep_research/`

说明：`ai_search` 后端接口不接收 `deep_think`，前端不得伪造该参数。

### 5.2 文件与历史

- session 临时文件上传：`POST /api/v1/chat/quick_parse`
- 知识库上传：`POST /api/v1/chat/upload_files`
- 知识库文件列表：`GET /api/v1/history/get_files`
- 知识库文件删除：`DELETE /api/v1/history/delete_file/{file_name}`
- 当前 session documents：`GET /api/v1/chat/sessions/{session_id}/documents`
- 当前 session summary：`GET /api/v1/chat/sessions/{session_id}/documents/summary`
- 历史 session：`GET /api/v1/history/get_sessions`
- 历史 messages：`GET /api/v1/history/get_messages?session_id=...`

### 5.3 仍非本轮目标

- 不新增 `/api/v1/assistant/*` UI 接入。
- 不做多知识库管理 UI。
- 不改后端接口和数据库迁移。
