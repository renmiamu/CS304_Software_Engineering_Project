# 前端 API 缺口台账

更新时间：2026-04-10  
维护目标：记录“前端目标能力仍需要，但后端当前源码尚未提供”的接口，同时注明哪些历史缺口已经被后端以其他接口部分补齐。  
事实来源：
- `docs/Frontend-develop-PLAN.md`
- `docs/frontend-backend-api.md`
- `docs/frontend-backend-api-requirements.md`
- `backend/app/api/v1/endpoints/**/*.py`

## 1. 当前结论（摘要）

- 后端已实现并可联调的真实能力，已经从旧文档里的 `auth + tis + bb + sync/all` 扩展到：
- `chat/*`
- `history/*`
- `user/interest`
- `bb/calendar/items` CRUD
- 当前前后端联调端口按 `http://localhost:9000`
- 但前端目标合约里仍有一批接口没有落地，尤其是统一命名的：
- `assistant/*`
- `profile`
- `dashboard/summary`
- `sources/*`

## 2. 已补齐的历史缺口

以下能力过去在文档里被当成“没有后端”，现在后端源码里已经有真实实现，只是命名和前端规划不完全一致：

### 2.1 聊天会话与消息历史

- 已实现：
- `POST /api/v1/chat/create_session`
- `POST /api/v1/chat/chat_on_docs`（SSE）
- `GET /api/v1/history/get_sessions`
- `GET /api/v1/history/get_messages`
- 结论：
- “完全没有会话后端”这个判断已经过时
- 但这些接口仍不是前端规划里的 `/api/v1/assistant/conversations*` 合约
- 当前前端已直接适配这套真实链路作为 Assistant 主链路，并在原模型选择器位置收缩为：
- `DeepSeek Chat` -> `deep_think=false`
- `DeepSeek R1` -> `deep_think=true`

### 2.2 文档上传与知识库文件历史

- 已实现：
- `POST /api/v1/chat/quick_parse`
- `POST /api/v1/chat/upload_files`
- `GET /api/v1/chat/get_parsed_content`
- `GET /api/v1/chat/sessions/{session_id}/documents`
- `GET /api/v1/chat/sessions/{session_id}/documents/summary`
- `GET /api/v1/history/get_files`
- `DELETE /api/v1/history/delete_file/{file_name}`
- 结论：
- “完全没有文档上传/文件历史接口”这个判断已经过时

### 2.3 Profile interest 持久化

- 已实现：
- `GET /api/v1/user/interest`
- `POST /api/v1/user/interest`
- `PATCH /api/v1/user/interest`
- `DELETE /api/v1/user/interest`
- 结论：
- `interest` 这个字段已经有后端读写能力，不应再继续被归类为“完全没有后端支持”
- 但完整的 `GET /api/v1/profile`、`PUT /api/v1/profile` 仍然没有

### 2.4 Schedule 手动日历项持久化

- 已实现：
- `GET /api/v1/bb/calendar/items`
- `POST /api/v1/bb/calendar/items`
- `PATCH /api/v1/bb/calendar/items/{ddl_id}`
- `DELETE /api/v1/bb/calendar/items/{ddl_id}`
- 结论：
- 如果前端未来要把本地 TODO 升级成服务端持久化，后端已有可复用基础接口

## 3. 当前仍然存在的缺口

## 3.1 Assistant 模块

前端规划目标仍未落地的统一合约：

- `GET /api/v1/assistant/conversations`
- `POST /api/v1/assistant/conversations`
- `GET /api/v1/assistant/conversations/{conversationId}`
- `PATCH /api/v1/assistant/conversations/{conversationId}`
- `DELETE /api/v1/assistant/conversations/{conversationId}`
- `POST /api/v1/assistant/conversations/{conversationId}/messages`
- `POST /api/v1/assistant/conversations/{conversationId}/messages/stream`
- `PATCH /api/v1/assistant/approvals/{id}`

现状说明：

- 后端已有 `chat/* + history/*`，当前前端也已用它覆盖“创建会话、文档对话、会话列表、消息历史”的主链路
- 但还没有：
- 前端当前设计要的 `/assistant/*` 统一命名
- 审批动作接口
- 规划里的 trace / approval 专用事件协议

## 3.3 Profile 模块

仍缺失：

- `GET /api/v1/profile`（目标聚合路径；当前实际读接口为 `GET /api/v1/user/profile`）
- `PUT /api/v1/profile`（偏好聚合写接口）

说明：

- `interest` 已通过 `/api/v1/user/interest` 对接，Profile 页提供 Interests 编辑与 Save
- 前端已移除 legacy preference 字段（goals/scheduleStyle 等 mock 模型）
- 其余 identity 字段仍为只读展示

## 3.4 Dashboard / Sources 聚合能力

仍缺失：

- `GET /api/v1/dashboard/summary`
- `GET /api/v1/sources`
- `GET /api/v1/sources/sync-jobs`
- `POST /api/v1/sources/{sourceId}/sync`

说明：

- 当前 Dashboard、Sources 仍主要靠前端组合 `bb/*`、`tis/*`、`sync/all`
- 后端还没有“统一摘要”和“单源同步/同步任务历史”标准接口

## 3.5 Schedule 标准化聚合接口

已实现：

- `GET /api/v1/schedule/events`（以及 POST/PATCH/DELETE）

说明：

- Schedule 页自定义事件 CRUD 已对接；TIS 课表仍来自 `POST /api/v1/tis/schedule`

## 3.6 Assistant 永久知识库多库能力

仍缺失：

- `GET /api/v1/assistant/knowledge-bases`
- `GET /api/v1/assistant/knowledge-bases/{knowledgeBaseId}/files`
- `POST /api/v1/assistant/knowledge-bases/{knowledgeBaseId}/files`

说明：

- 当前后端有“按用户/会话上传文件并聊天”的能力
- 但没有显式的“多知识库实体”管理接口

## 4. 前端临时策略

- 已实现接口：
- 直接按真实后端接入，或作为后续替换 mock 的候选能力
- 未实现的目标合约：
- 继续保留 mock 或显示“后端未接入”
- 不把历史命名接口误写成目标合约已经完成

## 5. 协作建议（给后端同学）

- 如果目标是尽快替换前端 mock，优先做决策而不是重复造轮子：
- 路线 A：直接把前端适配到现有 `chat/* + history/* + user/interest`
- 路线 B：保留当前前端目标设计，继续补齐标准化的 `assistant/* / profile`
- 无论选哪条路线，都建议先统一：
- 会话命名
- SSE 事件协议
- 文件上传后的资源模型
- Profile 偏好字段归属

## 6. 需要同步维护的事实

- 后端联调端口：`9000`
- 如果后端继续新增真实接口，必须同步更新：
- `docs/frontend-backend-api.md`
- `docs/frontend-api-gap.md`
- `docs/frontend-backend-api-requirements.md`

## 7. Assistant File Integration Update (2026-04-11)

- Frontend Assistant is no longer treating these as "backend not implemented":
- `quick_parse`
  - current-session temporary file upload
- `upload_files`
  - global knowledge upload entry
  - frontend now passes current `session_id` so uploads join the active conversation immediately
- `documents`
  - current-session read-only file list
- `documents/summary`
  - current-session read-only summary

- Remaining gaps:
- no dedicated global knowledge-base file list endpoint
- no dedicated global knowledge-base file management endpoint
- no standardized `/api/v1/assistant/knowledge-bases/*` multi-base contract

- Current frontend strategy:
- remove fake multi-knowledge-base UI
- keep Knowledge Base panel as upload + status + placeholder only
- keep Session Documents panel read-only and session-scoped

## 8. Frontend Reconnect Update (2026-04-22)

以下能力已经从“缺口或占位”移动到“前端已接真实历史接口”：

- Assistant 联网搜索：
  - `POST /api/v1/chat/ai_search/`
- Assistant Deep Research：
  - `POST /api/v1/chat/deep_research/`
- 全局知识库文件列表与删除：
  - `GET /api/v1/history/get_files`
  - `DELETE /api/v1/history/delete_file/{file_name}`
- session documents 与 summary：
  - `GET /api/v1/chat/sessions/{session_id}/documents`
  - `GET /api/v1/chat/sessions/{session_id}/documents/summary`
- 历史会话恢复：
  - `GET /api/v1/history/get_sessions`
  - `GET /api/v1/history/get_messages`
- 历史会话管理：
  - `PATCH /api/v1/history/sessions/{session_id}/rename`
  - `DELETE /api/v1/history/sessions/{session_id}`
- Profile interest：
  - `GET/POST/PATCH/DELETE /api/v1/user/interest`
- Schedule 手动任务 CRUD：
  - `GET/POST/PATCH/DELETE /api/v1/bb/calendar/items`

仍然存在的缺口：

- 标准化 `/api/v1/assistant/*` 合约仍未实现。
- 多知识库管理 UI 仍未实现。
- `profile` 完整偏好资源仍未实现；本轮只接 `interest`。

## 9. Sources Sync UI Update (2026-05-22)

- The frontend now includes Mail in the user-facing `Sync All Sources` flow, but this is frontend orchestration rather than one backend aggregate endpoint:
  - CAS data still uses `POST /api/v1/sync/all`;
  - Mail uses `POST /api/v1/mail/sync`.
- Still missing:
  - `GET /api/v1/sources`
  - `GET /api/v1/sources/sync-jobs`
  - `POST /api/v1/sources/{sourceId}/sync`
- BB and TIS `Sync CAS Info` buttons intentionally reuse `POST /api/v1/sync/all`. True BB-only or TIS-only sync remains a backend gap.
- Mail sync is not a gap: current frontend uses the existing `folder`, `limit`, and `unread_only` request fields exposed by `POST /api/v1/mail/sync`.

## 10. Profile Interests + Assistant Session Management Update (2026-05-23)

- Profile page now exposes an editable **Interests** field backed by `GET/POST/PATCH/DELETE /api/v1/user/interest`.
- Legacy frontend preference model (`UserProfile` goals/scheduleStyle/reminderPreference 等) 已删除。
- Assistant conversation list now supports:
  - `PATCH /api/v1/history/sessions/{session_id}/rename`（铅笔 + 行内编辑）
  - `DELETE /api/v1/history/sessions/{session_id}`（trash 删除，含已有 backend session）
- Still missing:
  - 聚合 `GET/PUT /api/v1/profile` 目标合约
  - 标准化 `/api/v1/assistant/*` 命名
