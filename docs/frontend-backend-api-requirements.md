# 前端后端接口需求总表（面向当前前端实现）

更新时间：2026-05-11
适用范围：`frontend/**` 当前页面与状态管理实现  
目标：把“前端当前需要什么”和“后端源码现在已经有什么”放到同一张表里，避免重复说错“后端没有”。

## 1. 当前后端状态

当前后端已实现并可复用的能力：

- 认证：`POST /api/v1/auth/login`、`POST /api/v1/auth/logout`
- 教务与 Blackboard：`/api/v1/tis/*`、`/api/v1/bb/*`
- 全量同步：`POST /api/v1/sync/all`
- 文档聊天与会话：`/api/v1/chat/*`
- 聊天历史与文件历史：`/api/v1/history/*`
- 用户兴趣持久化：`/api/v1/user/interest`
- 邮箱同步、读取与发送：`/api/v1/mail/*`

当前仍没有统一目标合约的模块：

- `Assistant` 标准化接口（`/api/v1/assistant/*`）
- `Profile` 完整偏好读写（`/api/v1/profile`）
- `Dashboard` 聚合摘要
- `Sources` 标准化源状态/任务历史/单源同步

联调端口统一口径：

- `http://localhost:9000`

## 2. 模块级需求总览

| 模块 | 后端当前已可用能力 | 前端可直接复用 | 仍缺能力 |
|---|---|---|---|
| Dashboard | `bb/calendar`、`bb/grades`、`bb/files`、`tis/schedule`、`tis/grade`、`tis/credit`、`sync/all` | 前端继续聚合已有数据 | `GET /api/v1/dashboard/summary` |
| Sources | `sync/all` + 各源读取接口 | 手动全量同步、结果汇总 | `GET /api/v1/sources`、`GET /api/v1/sources/sync-jobs`、`POST /api/v1/sources/{sourceId}/sync` |
| Assistant | `chat/create_session`、`chat/chat_on_docs`、`history/get_sessions`、`history/get_messages` | 当前前端已接入主聊天链路；模型切换收缩为 DeepSeek Chat / R1 | `/api/v1/assistant/*`、审批闭环 |
| Profile | `tis/info`、`tis/grade`、`user/interest` | identity 预填、GPA/Rank 展示、interest 持久化 | `GET /api/v1/profile`、`PUT /api/v1/profile` |

## 3. 已有后端能力（可直接纳入设计）

## 3.1 Schedule 可复用能力

后端已支持手动日历项持久化：

- `GET /api/v1/bb/calendar/items`
- `POST /api/v1/bb/calendar/items`
- `PATCH /api/v1/bb/calendar/items/{ddl_id}`
- `DELETE /api/v1/bb/calendar/items/{ddl_id}`

适用场景：

- 如果前端要把当前“本地 TODO”升级为账号级持久化，可直接评估复用这组接口

限制：

- 这组接口是日历项 CRUD，不是统一的 `schedule/events` 聚合层

## 3.2 Assistant 可复用能力

后端已支持：

- `POST /api/v1/chat/create_session`
- `POST /api/v1/chat/chat_on_docs`（SSE）
- `GET /api/v1/history/get_sessions`
- `GET /api/v1/history/get_messages`

当前前端已采用的真实映射：

- `DeepSeek Chat` -> `POST /api/v1/chat/chat_on_docs?...&deep_think=false`
- `DeepSeek R1` -> `POST /api/v1/chat/chat_on_docs?...&deep_think=true`

当前 SSE 实际事件协议：

- `message`
- `end`
- `error`

限制：

- 不是前端目标里的 `/api/v1/assistant/conversations/*`
- 没有审批动作接口
- 没有规划里的 `message.started / message.delta / trace.delta / approval.proposed / message.completed / message.error` 事件族

## 3.3 Knowledge Base 可复用能力

后端已支持：

- `POST /api/v1/chat/quick_parse`
- `POST /api/v1/chat/upload_files`
- `GET /api/v1/chat/get_parsed_content`
- `GET /api/v1/chat/sessions/{session_id}/documents`
- `GET /api/v1/chat/sessions/{session_id}/documents/summary`
- `GET /api/v1/history/get_files`
- `DELETE /api/v1/history/delete_file/{file_name}`

适用场景：

- 会话级上传文件
- 快速解析
- 文件历史查看与删除

限制：

- 知识库文件仍归 Assistant 文件流管理
- 没有稳定的任务进度、状态机、输出结果列表接口

## 3.4 Profile 可复用能力

后端已支持：

- `POST /api/v1/tis/info`
- `GET /api/v1/tis/grade`
- `GET /api/v1/user/interest`
- `POST /api/v1/user/interest`
- `PATCH /api/v1/user/interest`
- `DELETE /api/v1/user/interest`

适用场景：

- identity 预填
- GPA / Rank 展示
- `interest` 后端持久化

限制：

- 仍没有完整的偏好配置读写资源

## 4. A 类：必须新增的目标接口

## 4.1 Dashboard 聚合摘要

- `GET /api/v1/dashboard/summary`

建议响应：

```json
{
  "todayFocus": "string",
  "pendingTasks": 0,
  "pendingApprovals": 0,
  "connectedSources": 0,
  "totalSources": 3,
  "nextSyncLabel": "string"
}
```

## 4.2 Schedule 标准化聚合

- `GET /api/v1/schedule/events?from=...&to=...`

建议结构：

```ts
interface ScheduleEvent {
  id: string
  title: string
  source: 'tis' | 'bb' | 'manual'
  kind: 'course' | 'deadline' | 'task'
  startTime?: string
  endTime?: string
  weekday?: string
  timeSlots?: string
  location?: string
  teacher?: string
  weeks?: string
  metadata?: Record<string, unknown>
}

```

## 4.3 Sources 标准化

- `GET /api/v1/sources`
- `GET /api/v1/sources/sync-jobs?limit=...&cursor=...`
- `POST /api/v1/sources/{sourceId}/sync`

## 4.4 Assistant 标准化接口

### 4.4.1 会话管理

- `GET /api/v1/assistant/conversations`
- `POST /api/v1/assistant/conversations`
- `GET /api/v1/assistant/conversations/{conversationId}`
- `PATCH /api/v1/assistant/conversations/{conversationId}`
- `DELETE /api/v1/assistant/conversations/{conversationId}`

### 4.4.2 消息与流式输出

- `POST /api/v1/assistant/conversations/{conversationId}/messages`
- `POST /api/v1/assistant/conversations/{conversationId}/messages/stream`

### 4.4.3 审批动作

- `PATCH /api/v1/assistant/approvals/{approvalId}`

建议 SSE 事件协议：

- `message.started`
- `message.delta`
- `trace.delta`
- `approval.proposed`
- `message.completed`
- `message.error`

## 4.6 Profile 偏好配置

- `GET /api/v1/profile`
- `PUT /api/v1/profile`

建议结构：

```ts
interface UserProfile {
  major: string
  year: string
  goals: string
  scheduleStyle: string
  reminderPreference: string
  quietHours: string
  privacyNoticeAccepted: boolean
  bio: string
}
```

说明：

- 前端会继续用 `tis/info` 预填事实字段
- `profile` 只负责偏好配置持久化

## 5. B 类：需要先做路线决策的接口

以下不是“纯技术缺失”，而是“先决定是否复用现有后端”的问题：

### 5.1 Assistant 是否直接复用现有 `chat/* + history/*`

如果直接复用，前端需要自己做一层适配：

- 会话字段映射
- SSE 事件映射
- 文档聊天与普通助手对话的语义拆分

如果不复用，则后端继续建设标准化 `assistant/*`。

### 5.3 Profile 是否拆分为 `user/interest + profile`

当前 `interest` 已经独立落地在 `/api/v1/user/interest`。  
后续需要决定：

- 保持 `interest` 独立接口
- 还是并入未来的 `GET/PUT /api/v1/profile`

## 6. 对前端实现的直接建议

- 需要“尽快去 mock”的模块，优先评估复用现有真实接口，不要继续按旧文档假设后端完全没做
- 需要“长期稳定合约”的模块，继续推动标准化接口，不要把历史命名接口直接包装成已经达标
- 所有联调说明统一使用 `http://localhost:9000`

## 7. 2026-04-22 前端接入决策

本轮前端选择直接接入现有真实接口，不等待后端补标准化目标合约。

### 7.1 Assistant

- 普通对话继续使用 `chat_on_docs`。
- 勾选联网搜索后：
  - `Thinking` 使用 `ai_search`
  - `Deep Research` 使用 `deep_research`
  - `Fast` 禁用
- 未勾选联网搜索时：
  - `Fast` / `Thinking` 可用
  - `Deep Research` 禁用

### 7.2 文件、历史、知识库

- session 临时上传继续使用 `quick_parse`。
- 知识库上传继续使用 `upload_files`。
- 知识库 list/delete 使用 `history/get_files` 与 `history/delete_file/{file_name}`。
- session documents 使用 `chat/sessions/{session_id}/documents` 与 `documents/summary`。
- 历史恢复使用 `history/get_sessions` 与 `history/get_messages`。

### 7.3 Profile / Schedule

- Profile `interest` 使用 `/api/v1/user/interest`，不再以 localStorage 作为权威来源。
- Schedule 右侧手动任务 CRUD 使用 `/api/v1/bb/calendar/items`。

### 7.4 后续仍需后端决策

- 是否建设标准 `/api/v1/assistant/*`。
- 是否建设完整 `/api/v1/profile`。

## 8. Sources Sync UI Update (2026-05-22)

- Current frontend behavior:
  - `Sync All Sources` runs CAS data sync through `POST /api/v1/sync/all` and then Mail sync through `POST /api/v1/mail/sync`.
  - BB and TIS card-level `Sync CAS Info` buttons reuse `POST /api/v1/sync/all`.
  - Mail card-level `Sync Mail` calls `POST /api/v1/mail/sync` with user-selected `folder`, `limit`, and `unread_only`.
- Backend requirement still open:
  - add a source-level sync contract if product needs true per-source jobs, for example `POST /api/v1/sources/{sourceId}/sync`;
  - expose source/job state through `GET /api/v1/sources` and `GET /api/v1/sources/sync-jobs` if the frontend should stop maintaining this orchestration locally.
- Until those backend contracts exist, frontend must not describe BB/TIS buttons as true independent backend sync jobs.
