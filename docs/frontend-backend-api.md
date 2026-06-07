# 前后端 API 对接文档（按后端真实实现）

更新时间：2026-05-11
适用后端：`backend/app/**/*.py` 当前实现  
说明：本文件只记录“后端源码已经实现”的接口；前端联调、mock 替换、缺口判断都以这里为准。

## 1. 当前可用接口总览

### 1.1 基础接口

- `GET /`
- `GET /health`

### 1.2 认证（`/api/v1/auth`）

- `GET /api/v1/auth/services`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`

### 1.3 TIS（`/api/v1/tis`）

- `POST /api/v1/tis/schedule`
- `GET /api/v1/tis/grade`
- `GET /api/v1/tis/credit`
- `POST /api/v1/tis/info`
- `GET /api/v1/tis/id`
- `POST /api/v1/tis/photo`

### 1.4 Blackboard（`/api/v1/bb`）

- `POST /api/v1/bb/courses`
- `POST /api/v1/bb/calendar`
- `GET /api/v1/bb/calendar/items`
- `POST /api/v1/bb/calendar/items`
- `PATCH /api/v1/bb/calendar/items/{ddl_id}`
- `DELETE /api/v1/bb/calendar/items/{ddl_id}`
- `POST /api/v1/bb/grades`
- `POST /api/v1/bb/files`

### 1.5 同步（`/api/v1/sync`）

- `POST /api/v1/sync/all`

### 1.6 用户偏好（`/api/v1/user`）

- `GET /api/v1/user/interest`
- `POST /api/v1/user/interest`
- `PATCH /api/v1/user/interest`
- `DELETE /api/v1/user/interest`

### 1.7 聊天与知识库（`/api/v1/chat`）

- `POST /api/v1/chat/create_session`
- `POST /api/v1/chat/quick_parse`
- `POST /api/v1/chat/upload_files`
- `GET /api/v1/chat/get_parsed_content`
- `POST /api/v1/chat/chat_on_docs`
- `GET /api/v1/chat/sessions/{session_id}/documents`
- `GET /api/v1/chat/sessions/{session_id}/documents/summary`

### 1.8 历史记录（`/api/v1/history`）

- `GET /api/v1/history/get_files`
- `DELETE /api/v1/history/delete_file/{file_name}`
- `GET /api/v1/history/get_messages`
- `GET /api/v1/history/get_sessions`
- `PATCH /api/v1/history/sessions/{session_id}/rename`
- `DELETE /api/v1/history/sessions/{session_id}`

### 1.9 邮箱（`/api/v1/mail`）

- `GET /api/v1/mail/account`
- `POST /api/v1/mail/account/login`
- `POST /api/v1/mail/account/logout`
- `POST /api/v1/mail/send`
- `POST /api/v1/mail/sync`
- `GET /api/v1/mail/messages`
- `GET /api/v1/mail/messages/{mail_id}`

## 2. 全局约定

### 2.1 Base URL 与端口

- 业务接口统一前缀：`/api/v1`
- 当前本地前后端联调统一按 `http://localhost:9000`
- 事实依据：
- `backend/app/main.py` 在直接执行 `python backend/app/main.py` 且未设置 `PORT` 时，代码兜底值是 `9000`
- `backend/docker-compose.yml` 仍然暴露 `8000:8000`
- `backend/docker-compose.yml` 的启动命令仍然是 `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- 因此本仓库当前文档按你实际联调端口 `9000` 记录；如果改走 `docker-compose`，端口口径需要再切回 `8000`

### 2.2 鉴权

- 登录成功后返回：
- `access_token`
- `token_type`（固定为 `bearer`）
- Bearer Token 当前由 `OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')` 解析
- JWT 默认有效期约 15 分钟，`sub` 为登录时提交的学号字符串

需要 `Authorization: Bearer <access_token>` 的接口：

- `POST /api/v1/tis/schedule`
- `GET /api/v1/tis/grade`
- `GET /api/v1/tis/credit`
- `POST /api/v1/tis/photo`
- `POST /api/v1/bb/calendar`
- `GET /api/v1/bb/calendar/items`
- `POST /api/v1/bb/calendar/items`
- `PATCH /api/v1/bb/calendar/items/{ddl_id}`
- `DELETE /api/v1/bb/calendar/items/{ddl_id}`
- `POST /api/v1/bb/grades`
- `POST /api/v1/bb/files`
- `POST /api/v1/sync/all`
- `GET /api/v1/user/interest`
- `POST /api/v1/user/interest`
- `PATCH /api/v1/user/interest`
- `DELETE /api/v1/user/interest`
- 全部 `chat/*`
- 全部 `history/*`
- 全部 `mail/*`

当前不强制 Bearer 的接口：

- `GET /api/v1/auth/services`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `POST /api/v1/tis/info`
- `GET /api/v1/tis/id`
- `POST /api/v1/bb/courses`

### 2.3 请求格式

- `POST /api/v1/auth/login`：`application/x-www-form-urlencoded`
- `POST /api/v1/chat/quick_parse`：`multipart/form-data`
- `POST /api/v1/chat/upload_files`：`multipart/form-data`
- `POST /api/v1/mail/account/login`：`application/json`
- `POST /api/v1/mail/send`：`application/json`
- `POST /api/v1/mail/sync`：`application/json`
- 其他 POST/PATCH 接口默认 `application/json`

### 2.4 通用错误

- 大部分接口遵循 FastAPI 默认结构：

```json
{
  "detail": "错误描述"
}
```

- 少数接口会返回对象型 `detail`，例如 `POST /api/v1/chat/upload_files` 在“全部文件都失败”时会返回失败明细对象，前端不能把 `detail` 强写死成字符串。

## 3. 接口详情

## 3.1 基础健康接口

### `GET /`

```json
{ "message": "Backend is running" }
```

### `GET /health`

```json
{ "status": "ok" }
```

## 3.2 认证接口（`/api/v1/auth`）

### `GET /api/v1/auth/services`

```json
{
  "services": {
    "tis": "https://tis.sustech.edu.cn/cas",
    "bb": "https://bb.sustech.edu.cn/webapps/bb-sso-BBLEARN/index.jsp",
    "mail": "https://mail.sustech.edu.cn/"
  }
}
```

### `POST /api/v1/auth/login`

- Query：
- `service` 可选，默认 `all`
- 支持值：`all | both | bb | tis | blackboard | mail`
- Header：
- `Content-Type: application/x-www-form-urlencoded`
- Form：
- `username`（必填）
- `password`（必填）

聚合登录示例响应：

```json
{
  "message": "login success",
  "service": "all",
  "services": {
    "bb": { "is_valid": true, "cookies": { "...": "..." } },
    "tis": { "is_valid": true, "cookies": { "...": "..." } }
  },
  "user_init": { "ok": true, "user_id": 12210001, "created": false },
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

单服务登录示例响应：

```json
{
  "message": "login success",
  "service": "tis",
  "cookies": {
    "<cookie-name>": "<cookie-value>"
  },
  "user_init": { "ok": true, "user_id": 12210001, "created": false },
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

常见错误：

- `400`：不支持的 `service`，或用户名/密码为空
- `401`：CAS 认证失败
- `422`：表单字段缺失
- `500`：登录流程内部异常
- `502`：CAS 服务不可用

### `POST /api/v1/auth/logout`

```json
{ "message": "logout success" }
```

说明：当前是无状态占位接口，不会回收服务端会话。

## 3.3 TIS 接口（`/api/v1/tis`）

通用 Query：

- `cookies_file` 可选，默认 `clients/resources/cookies.json`

### `POST /api/v1/tis/schedule`

请求体：

```json
{
  "xn": "2025-2026",
  "xq": "2",
  "bs": "2"
}
```

响应：

```json
{
  "courses": [
    {
      "course_name": "线性代数",
      "teacher": "张三",
      "weekday": "星期一",
      "weeks": "1-16周",
      "location": "教学楼101",
      "time_slots": "1-2节"
    }
  ]
}
```

说明：

- 当前实现读取本地数据库中的已同步课表
- `xn/xq/bs` 目前有默认值，但服务层当前不按这三个字段过滤数据库结果

### `GET /api/v1/tis/grade`

```json
{
  "GPA": 3.76,
  "Rank": "15/320"
}
```

### `GET /api/v1/tis/credit`

```json
{
  "total_credit": 84.0,
  "category_credit": {
    "必修": 52.0,
    "选修": 32.0
  }
}
```

### `POST /api/v1/tis/info`

请求体：

```json
{
  "page": 1,
  "limit": 100,
  "sort": "id",
  "order": "desc"
}
```

响应结构：

```json
{
  "data": {
    "...": "..."
  }
}
```

说明：`data` 在 schema 中允许是对象或对象数组，前端不要把它写死成单一形态。

### `GET /api/v1/tis/id`

```json
{ "tis_id": "12210001" }
```

### `POST /api/v1/tis/photo`

```json
{
  "base64": "<base64-string>",
  "filename": "photo.jpg",
  "size": 12345,
  "type": "image/jpeg",
  "saved_path": "..."
}
```

## 3.4 Blackboard 接口（`/api/v1/bb`）

### `POST /api/v1/bb/courses`

请求体：

```json
{
  "term_filter": "2026春"
}
```

响应：

```json
{
  "courses": [
    {
      "title": "CS203",
      "course_id": "2026-CS203",
      "url": "https://..."
    }
  ]
}
```

### `POST /api/v1/bb/calendar`

请求体可省略；传值时结构如下：

```json
{
  "start_timestamp": 1743350400,
  "end_timestamp": 1746038799
}
```

响应：

```json
{
  "events": [
    {
      "completed": false,
      "color": "#ef4444",
      "userCreated": false,
      "calendarName": "Blackboard",
      "end": "2026-04-15T23:59:00",
      "title": "Homework 3",
      "eventType": "deadline"
    }
  ]
}
```

### `GET /api/v1/bb/calendar/items`

说明：返回当前用户在数据库中的 DDL/日历项，不是 Blackboard 远端拉取接口。

```json
{
  "events": [
    {
      "id": 1,
      "completed": false,
      "color": "#ef4444",
      "userCreated": true,
      "calendarName": "Manual",
      "end": "2026-04-20T23:59:00",
      "title": "Prepare slides",
      "eventType": "task"
    }
  ]
}
```

### `POST /api/v1/bb/calendar/items`

请求体：

```json
{
  "title": "Prepare slides",
  "end": "2026-04-20T23:59:00",
  "completed": false,
  "color": "#ef4444",
  "calendarName": "Manual",
  "eventType": "task",
  "userCreated": true
}
```

响应：返回创建后的单个 `BBCalendarItem`。

### `PATCH /api/v1/bb/calendar/items/{ddl_id}`

请求体为部分更新，允许字段：

- `title`
- `end`
- `completed`
- `color`
- `calendarName`
- `eventType`
- `userCreated`

响应：返回更新后的单个 `BBCalendarItem`。

### `DELETE /api/v1/bb/calendar/items/{ddl_id}`

```json
{ "deleted": true, "id": 12 }
```

### `POST /api/v1/bb/grades`

请求体：

```json
{
  "term_filter": "2026春"
}
```

响应：

```json
{
  "grades": [
    {
      "course_id": "CS203",
      "course_name": "概率论",
      "item_name": "Homework 1",
      "full_grade": "95"
    }
  ]
}
```

### `POST /api/v1/bb/files`

请求体：

```json
{
  "term_filter": "2026春"
}
```

响应：

```json
{
  "files": [
    {
      "course": "CS203",
      "content": "Lecture 03",
      "file_url": "https://...",
      "file_name": "lecture03.pdf"
    }
  ]
}
```

## 3.5 同步接口（`/api/v1/sync`）

### `POST /api/v1/sync/all`

Query：

- `cookies_file` 可选，默认 `clients/resources/cookies.json`

响应结构：

```json
{
  "user_id": 12311011,
  "sync_summary": {
    "tis": {
      "schedule": { "ok": true, "data": {} },
      "grade": { "ok": true, "data": {} },
      "credit": { "ok": true, "data": {} },
      "photo": { "ok": true, "data": {} }
    },
    "bb": {
      "calendar": { "ok": true, "data": {} },
      "grades": { "ok": true, "data": {} },
      "files": { "ok": true, "data": {} }
    }
  }
}
```

说明：

- 每个子任务都包一层 `{ ok, data }` 或 `{ ok, status_code, error }`
- 即使部分子任务失败，整个接口仍会返回汇总对象，不会因为某一项失败直接整体 500

## 3.6 用户偏好接口（`/api/v1/user`）

### `GET /api/v1/user/interest`

```json
{
  "user_id": 12311011,
  "interest": "LLM, football, startup"
}
```

### `POST /api/v1/user/interest`

### `PATCH /api/v1/user/interest`

请求体：

```json
{
  "interest": "LLM, football, startup"
}
```

响应：

```json
{
  "user_id": 12311011,
  "interest": "LLM, football, startup"
}
```

### `DELETE /api/v1/user/interest`

```json
{
  "user_id": 12311011,
  "interest": null
}
```

## 3.7 聊天与知识库接口（`/api/v1/chat`）

说明：这组接口是真实已实现的“文档聊天/知识库”能力，但路径和数据结构仍是历史命名，不等于前端规划里的 `/assistant/*` 合约。

### `POST /api/v1/chat/create_session`

```json
{
  "session_id": "0f8fad5bd9cb469f",
  "status": "success",
  "message": "Session created successfully"
}
```

### `POST /api/v1/chat/quick_parse`

- Query：
- `session_id` 必填
- Form：
- `file` 必填，单文件上传

说明：

- 用于当前会话的快速文档解析
- 返回值由 `quick_parse_service` 决定，源码未用 schema 固定字段，前端不能假设稳定 JSON 结构

### `POST /api/v1/chat/upload_files`

- Query：
- `session_id` 可选；不传时后端会退回使用 `user_id` 作为 `session_id`
- Form：
- `files` 必填，支持多文件

全成功响应：

```json
{
  "status": "success",
  "message": "所有文件解析成功",
  "successful_files": ["lecture03.pdf"],
  "total_files": 1
}
```

部分成功响应：

```json
{
  "status": "partial_success",
  "message": "部分文件解析成功，1 个成功，1 个失败",
  "successful_files": ["lecture03.pdf"],
  "failed_files": ["broken.pdf: 文件解析失败 - ..."],
  "total_files": 2
}
```

说明：

- 如果全部失败，接口会抛 `400`，`detail` 为失败详情对象
- 后端会拒绝同一用户下同名文件重复上传

### `GET /api/v1/chat/get_parsed_content`

- Query：
- `session_id` 必填

说明：返回快速解析后的缓存内容，响应 shape 未在 schema 中固定。

### `POST /api/v1/chat/chat_on_docs`

- Query：
- `session_id` 必填
- `deep_think` 可选，默认 `false`
- `false` 时使用 `deepseek-chat`
- `true` 时使用 `deepseek-reasoner`
- Body：

```json
{
  "message": "请总结这份文档"
}
```

- 响应类型：`text/event-stream`

当前 SSE 事件名：

- `message`
- `end`
- `error`

`message` 事件实际会推送三类 JSON：

```json
{ "documents": [] }
```

```json
{ "role": "assistant", "content": "token chunk", "thinking": false }
```

```json
{ "recommended_questions": ["..."] }
```

前端当前真实接入方式：

- `DeepSeek Chat` -> `deep_think=false`
- `DeepSeek R1` -> `deep_think=true`
- 当 `thinking=true` 时，前端按“推理流”单独渲染，不映射到旧 trace 系统

结束事件：

```text
event: end
data: [DONE]
```

### `GET /api/v1/chat/sessions/{session_id}/documents`

```json
{
  "session_id": "0f8fad5bd9cb469f",
  "has_documents": true,
  "documents": [
    {
      "id": 1,
      "session_id": "0f8fad5bd9cb469f",
      "document_name": "lecture03.pdf",
      "document_type": "pdf",
      "file_size": 1024,
      "upload_time": "2026-04-10T10:00:00",
      "created_at": "2026-04-10T10:00:00",
      "updated_at": "2026-04-10T10:00:00"
    }
  ],
  "total_count": 1
}
```

### `GET /api/v1/chat/sessions/{session_id}/documents/summary`

```json
{
  "session_id": "0f8fad5bd9cb469f",
  "has_documents": true,
  "latest_document_name": "lecture03.pdf",
  "latest_document_type": "pdf",
  "latest_upload_time": "2026-04-10T10:00:00",
  "total_documents": 1
}
```

## 3.8 历史记录接口（`/api/v1/history`）

说明：这组接口为聊天历史和知识库文件历史服务，同样是当前真实实现，不等于前端规划中的 `/assistant/conversations*` 命名。

### `GET /api/v1/history/get_files`

```json
[
  {
    "user_id": "12311011",
    "file_name": "lecture03.pdf",
    "created_at": "2026-04-10T10:00:00",
    "updated_at": "2026-04-10T10:00:00"
  }
]
```

### `DELETE /api/v1/history/delete_file/{file_name}`

```json
{
  "message": "Successfully deleted 1 document(s) from ES and database"
}
```

说明：`file_name` 会先 URL decode，再按当前用户删除。

### `GET /api/v1/history/get_messages`

- Query：
- `session_id` 必填

响应：

```json
[
  {
    "message_id": "uuid",
    "session_id": "0f8fad5bd9cb469f",
    "user_question": "请总结这份文档",
    "model_answer": "总结内容",
    "documents": [],
    "recommended_questions": [],
    "think": "推理片段",
    "created_at": "2026-04-10 10:00:00"
  }
]
```

### `GET /api/v1/history/get_sessions`

```json
{
  "user_id": "12311011",
  "sessions": [
    {
      "session_id": "0f8fad5bd9cb469f",
      "session_name": "session-0f8fad5bd9cb469f",
      "user_id": "12311011",
      "created_at": "2026-04-10 10:00:00",
      "updated_at": "2026-04-10 10:00:00"
    }
  ]
}
```

## 3.9 邮箱接口（`/api/v1/mail`）

说明：这组接口目前用 IMAP 收邮件，用 SMTP 发邮件。现在邮箱账号和密码不再放在 `.env` 里，而是先调用邮箱登录接口。登录后，同一用户后续的发送、同步、查看邮件都会使用当前登录的邮箱账号。退出邮箱账号后，邮箱相关操作会返回未登录。

当前后端只从 `.env` 读取服务器地址和端口：

- `QQ_MAIL_IMAP_HOST`：QQ 邮箱 IMAP 服务器地址，默认 `imap.qq.com`
- `QQ_MAIL_IMAP_PORT`：QQ 邮箱 IMAP SSL 端口，默认 `993`
- `QQ_MAIL_SMTP_HOST`：QQ 邮箱 SMTP 服务器地址，默认 `smtp.qq.com`
- `QQ_MAIL_SMTP_PORT`：QQ 邮箱 SMTP SSL 端口，默认 `465`
- `EXMAIL_IMAP_HOST`：腾讯企业邮箱 IMAP 服务器地址，默认 `imap.exmail.qq.com`
- `EXMAIL_IMAP_PORT`：腾讯企业邮箱 IMAP SSL 端口，默认 `993`
- `EXMAIL_SMTP_HOST`：腾讯企业邮箱 SMTP 服务器地址，默认 `smtp.exmail.qq.com`
- `EXMAIL_SMTP_PORT`：腾讯企业邮箱 SMTP SSL 端口，默认 `465`
- `QQ_MAIL_FETCH_TIMEOUT_SECONDS`：收件超时时间，可选
- `QQ_MAIL_SEND_TIMEOUT_SECONDS`：发件超时时间，可选

### `POST /api/v1/mail/account/login`

用途：登录一个邮箱账号。当前后端同一用户同一时间只保留一个邮箱账号；再次登录会覆盖旧账号。

请求体：

```json
{
  "provider": "qq",
  "email_address": "student@qq.com",
  "password": "mail-auth-code"
}
```

字段说明：

- `provider` 可选，支持 `qq` 和 `exmail`，默认 `qq`
- `email_address` 必填，邮箱账号
- `password` 必填，QQ 邮箱这里一般填写 IMAP/SMTP 授权码；腾讯企业邮箱填写客户端专用密码或管理员允许的邮箱密码

成功响应：

```json
{
  "logged_in": true,
  "provider": "qq",
  "mailbox": "student@qq.com",
  "logged_in_at": "2026-05-14T10:00:00"
}
```

### `GET /api/v1/mail/account`

用途：查看当前是否已经登录邮箱账号。不会返回密码。

未登录时：

```json
{
  "logged_in": false,
  "provider": null,
  "mailbox": null,
  "logged_in_at": null
}
```

### `POST /api/v1/mail/account/logout`

用途：退出当前邮箱账号。退出后，发送、同步、查看邮件详情等邮箱操作都需要重新登录邮箱账号。

成功响应：

```json
{
  "logged_out": true,
  "mailbox": "student@qq.com"
}
```

### `POST /api/v1/mail/send`

用途：通过 SMTP 发送邮件。这个接口不会把发送内容写进数据库，只负责把邮件发出去。

请求体：

```json
{
  "to_addresses": ["teacher@example.com"],
  "cc_addresses": [],
  "bcc_addresses": [],
  "subject": "Test mail",
  "body": "Hello, this is a test mail.",
  "html_body": null
}
```

完整字段说明：

- `to_addresses` 必填，收件人列表
- `cc_addresses` 可选，抄送列表
- `bcc_addresses` 可选，密送列表
- `subject` 必填，邮件标题
- `body` 可选，纯文本正文
- `html_body` 可选，HTML 正文。只传 `html_body` 时，后端会自动生成一份纯文本正文

成功响应：

```json
{
  "mailbox": "studentid@mail.sustech.edu.cn",
  "to_addresses": ["teacher@example.com"],
  "cc_addresses": [],
  "bcc_count": 0,
  "subject": "Test mail",
  "message_id": "<mail-message-id@mail.sustech.edu.cn>",
  "sent_at": "2026-05-11T16:30:00"
}
```

常见失败：

- `400`：收件人、标题或正文缺失，或者收件人地址格式明显不对
- `401`：邮箱账号未登录，或 SMTP 登录失败
- `404`：当前 token 对应的用户在数据库里不存在
- `502`：SMTP 服务器连接失败或发送失败
- `504`：SMTP 请求超时

### `POST /api/v1/mail/sync`

用途：从当前已登录邮箱账号的 IMAP 文件夹同步邮件到数据库。QQ 邮箱和腾讯企业邮箱都走这个接口，具体服务器配置由邮箱登录时的 `provider` 决定。

请求体：

```json
{
  "folder": "INBOX",
  "limit": 1,
  "unread_only": false
}
```

完整字段说明：

- `folder` 可选，默认 `INBOX`
- `limit` 可选，默认 `20`，范围 `1-100`
- `unread_only` 可选，默认 `false`；为 `true` 时只同步未读邮件

成功响应：

```json
{
  "mailbox": "student@qq.com",
  "folder": "INBOX",
  "requested_limit": 1,
  "unread_only": false,
  "fetched": 1,
  "inserted": 1,
  "updated": 0
}
```

常见失败：

- `400`：文件夹打开失败，例如 `Failed to open folder: INBOX`
- `401`：邮箱账号未登录，或 IMAP 登录失败
- `404`：当前 token 对应的用户在数据库里不存在
- `502`：IMAP 服务器连接失败或搜索失败
- `504`：IMAP 请求超时

### `GET /api/v1/mail/messages`

用途：读取当前登录邮箱账号已经同步进数据库的邮件列表。这个接口不主动连接邮箱服务器，只查本地数据库。

Query 参数：

- `mailbox` 可选；如果传入，必须等于当前登录邮箱账号
- `folder` 可选，按文件夹过滤
- `limit` 可选，默认 `50`，范围 `1-200`

成功响应：

```json
{
  "messages": [
    {
      "id": 1,
      "mailbox": "student@qq.com",
      "folder": "INBOX",
      "imap_uid": "123",
      "message_id": "<mail-message-id>",
      "subject": "邮件主题",
      "from_address": "Sender <sender@example.com>",
      "to_address": "student@qq.com",
      "cc_address": null,
      "received_at": "2026-05-09T10:00:00",
      "raw_date": "Sat, 09 May 2026 10:00:00 +0800",
      "snippet": "邮件摘要",
      "text_body": "纯文本正文",
      "html_body": "<html>...</html>",
      "is_seen": false,
      "has_attachment": false,
      "synced_at": "2026-05-09T10:01:00"
    }
  ]
}
```

### `GET /api/v1/mail/messages/{mail_id}`

用途：读取当前登录邮箱账号下某一封已同步邮件的完整内容。

Path 参数：

- `mail_id`：邮件在数据库里的自增 ID

成功响应结构与 `GET /api/v1/mail/messages` 里的单个 `messages` 元素一致。

常见失败：

- `401`：邮箱账号未登录
- `404`：该邮件不存在，或不属于当前登录邮箱账号

## 4. 对前端的直接影响

- 现在后端已经不只是 `auth/tis/bb/sync` 四类接口，还新增了：
- 文档聊天与会话：`chat/*`
- 文档与消息历史：`history/*`
- 用户兴趣持久化：`user/interest`（Profile 页唯一可写字段）
- 用户档案读取：`GET /user/profile`（identity 展示）
- Blackboard 日历项 CRUD：`bb/calendar/items`
- 邮箱登录、同步、读取与发送：`mail/*`
- 因为当前新增能力多为“历史命名”接口，前端如果要接入，需要先决定是：
- 直接适配现有 `chat/* + history/* + user/interest + mail/*`
- 还是继续等新的 `assistant/* / profile` 目标合约

## 5. Frontend Integration Update (2026-04-11)

- Assistant has now connected the real file flow:
- `POST /api/v1/chat/quick_parse`
  - used for current-session temporary files
- `POST /api/v1/chat/upload_files`
  - still the global knowledge upload entry
  - Assistant now always sends the current `session_id`
  - uploaded files are expected to join the current conversation immediately
- `GET /api/v1/chat/sessions/{session_id}/documents`
  - used by the read-only Session Documents panel
- `GET /api/v1/chat/sessions/{session_id}/documents/summary`
  - used by the read-only Session Documents panel summary
- `GET /api/v1/chat/get_parsed_content`
  - treated as weakly typed helper data only

- Still missing for frontend:
- a stable global knowledge-base file list endpoint
- global knowledge-base file management endpoints

- Therefore current frontend behavior is intentionally:
- Knowledge Base panel = upload entry + status only
- global history list = empty placeholder until backend list APIs exist

## 6. Frontend Integration Update (2026-04-22)

This round connects the frontend to additional existing backend APIs without changing `backend/**`.

### 6.1 Assistant message endpoints

- Web search off:
  - `Fast` calls `POST /api/v1/chat/chat_on_docs?deep_think=false`
  - `Thinking` calls `POST /api/v1/chat/chat_on_docs?deep_think=true`
  - `Deep Research` is disabled
- Web search on:
  - `Fast` is disabled
  - `Thinking` calls `POST /api/v1/chat/ai_search/`
  - `Deep Research` calls `POST /api/v1/chat/deep_research/`

`ai_search` has no `deep_think` query parameter in the backend implementation.

### 6.2 Assistant files and history

- `GET /api/v1/history/get_files` is now the current global knowledge-file list.
- `DELETE /api/v1/history/delete_file/{file_name}` is now the current knowledge-file delete path.
- `GET /api/v1/chat/sessions/{session_id}/documents` powers the session documents panel.
- `GET /api/v1/chat/sessions/{session_id}/documents/summary` powers the session summary refresh.
- `GET /api/v1/history/get_sessions` and `GET /api/v1/history/get_messages` power history restore.

### 6.3 Profile and Schedule database-backed APIs

- `GET/POST/PATCH/DELETE /api/v1/user/interest` backs Profile interests. Frontend treats `/user/interest` as the writable source of truth.
- `GET/POST/PATCH/DELETE /api/v1/bb/calendar/items` backs the Schedule right-side manual task CRUD.

### 6.4 Still not equivalent to target contracts

The current real integration still does not mean these target contracts exist:

- `/api/v1/assistant/*`
- `/api/v1/profile`
- `/api/v1/schedule/events`

## 7. Frontend Assistant Citation Integration Update (2026-05-05)

- Assistant frontend now consumes `documents` from `POST /api/v1/chat/chat_on_docs` SSE `message` events as citation sources for the assistant message.
- Citation markers in model text keep the backend format semantically and support both `##N$$` and `##引用N##`; the UI renders them as compact clickable `[N]` markers.
- Sources render in the Assistant right-side panel alongside Knowledge Base and Session Documents. Clicking a citation opens that panel and highlights the full source card.
- `recommended_questions` from SSE and `GET /api/v1/history/get_messages` are parsed from either JSON arrays or JSON strings and displayed as clickable follow-up question chips.
- After a message completes, the frontend refreshes backend sessions and adopts a non-default backend `session_name`; default names like `session-<session_id>` do not overwrite the local title.

## 8. Sources Sync UI Update (2026-05-22)

- `/sources` keeps using `POST /api/v1/sync/all` for CAS-backed data. That backend response covers `tis` and `bb`; it does not include `mail`.
- `/sources` now treats `Sync All Sources` as a frontend orchestration entry:
  - first call `POST /api/v1/sync/all` for BB/TIS;
  - then call `POST /api/v1/mail/sync` for Mail when a mailbox is connected.
- The Mail card sends the existing backend request shape:

```json
{
  "folder": "INBOX",
  "limit": 20,
  "unread_only": false
}
```

- Mail sync controls expose:
  - `folder`: default `INBOX`;
  - `limit`: selectable `10 / 20 / 50 / 100`; backend default remains `20`, backend range remains `1-100`;
  - `unread_only`: checkbox mapped to backend `unread_only`.
- BB and TIS cards show `Sync CAS Info`, but this is not a true single-source backend call. Both buttons reuse `POST /api/v1/sync/all` because no `POST /api/v1/sources/{sourceId}/sync` endpoint exists yet.

## 9. Schedule Custom Event Display Update (2026-05-22)

- `/schedule` reads custom schedule blocks from `GET /api/v1/schedule/events`.
- Frontend excludes only records whose normalized `schedule_type` is exactly `course`.
- Non-course records with an empty or missing `schedule_type` are displayed as `custom` events.
- The Schedule page visible UI labels are English-only; Chinese weekday and class-slot parsing remains an internal compatibility layer for backend/TIS data.

## 10. Profile Interests + Assistant Session Management Update (2026-05-23)

- `/profile` adds an **Interests** editor with Save, backed by `/api/v1/user/interest`.
- Identity display remains read-only via `GET /api/v1/user/profile` → `identityCard`.
- Legacy frontend preference fields (`goals`, `scheduleStyle`, etc.) were removed from the client model.
- Assistant conversation sidebar now calls:
  - `PATCH /api/v1/history/sessions/{session_id}/rename` with `{ session_name }`
  - `DELETE /api/v1/history/sessions/{session_id}`
- Draft conversations without a backend `session_id` still rename/delete locally only until the first backend session is created.
