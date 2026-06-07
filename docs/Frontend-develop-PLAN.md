## Study Copilot 移除记录（2026-05-20）

- 已移除 `/study` 页面、Study 导航入口、上传资料状态、生成结果状态、Dashboard 学习产物摘要。
- 当前前端页面集不包含 Study Copilot；除非明确恢复该功能，否则不要再新增 `/study` 引用。

## Summary
- 页面定版：`Dashboard / Schedule(新增) / Assistant / Sources / Profile`（已移除 `/study` 页面）。
- 已确认关键规则全部固化：审批仅 Assistant、Trace 仅流式且完成即消失、Approve 后立即执行、Reject 原因可选、无审批超时、Campus 必须带引用、Schedule 仅直接编辑本地 TODO。

## 最新落地基线（2026-04-04）

- 本轮仅改前端，不新增后端接口；UI 文案保持英文。
- Dashboard：
- `Upcoming Deadlines` 显示所有未来 DDL，按截止时间升序；列表超过 10 条时仅展示前 10 条。
- 删除 `Live Source Snapshot`、删除 `Approval Queue`。
- 统计修复：待审批汇总改为读取会话内真实审批状态（跨会话聚合）。
- Schedule（新增页面）：
- 数据来源：`tis/schedule` + `bb/calendar`。
- Sources：
- 删除 `Backend Snapshot`。
- 保留运维控制台：连接状态、同步任务、手动 `sync/all`。
- 新增明细列表：DDL 明细、成绩明细、文件资源明细（不再只显示计数）。
- Profile：
- 删除 `Academic Snapshot`、`Today's Schedule`、`Academic Profile` 业务卡。
- 保留偏好编辑。
- 新增只读身份信息区（姓名/学号/联系方式/生日/院系等，缺失显示 `-`）。
- Assistant：
- 审批仅消息内处理。
- trace 仅在流式阶段显示，完成立即移除。

## 页面设计定版
1. Dashboard
- 仅分流跳转，不做重操作。

2. Schedule（新增）
- 视图：周+月，默认周视图，周起始日周一。
- 主日历：
- 周视图固定 10 节（Mon-Sun x 10 slots），跨节课程按连续块渲染。
- 月视图固定 7 列日历格，每日最多显示 2 条并展示 `+N more`。
- 导航：`Prev / Today / Next`，并将 `view/date` 同步到 URL query（`?view=week|month&date=YYYY-MM-DD`）。
- 切换动效：轻量淡入+轻位移（约 220ms），兼容 `prefers-reduced-motion`。
- 学期起始锚点：`2026-02-23`（周一），用于“第 N 周 + 星期几”映射具体日期。
- 节次时间固定：
- `1 08:00-08:50`、`2 09:00-09:50`、`3 10:20-11:10`、`4 11:20-12:10`
- `5 14:00-14:50`、`6 15:00-15:50`、`7 16:20-17:10`、`8 17:20-18:10`
- `9 19:00-19:50`、`10 20:00-20:50`
- 右侧栏：
- **Custom Events** 走 `GET/POST/PATCH/DELETE /api/v1/schedule/events`（周课表块，不是 deadline）。
- **Deadlines** 走 `GET/POST/PATCH/DELETE /api/v1/bb/calendar/items`（due-date 任务；含 BB 同步与手动添加，可标记完成/删除）。
- Dashboard Quick Launch 提供 `Manage Deadlines` 入口，深链到 `/schedule#deadlines`。

3. Assistant
- 结构：会话侧栏 + 主聊天区（模式/模型、消息流、输入区）。
- Trace：仅 streaming 阶段显示，完成即消失。
- 审批：仅消息内卡片，`pending -> approved -> executing -> succeeded/failed` 或 `pending -> rejected`。
- Reject 提供预置原因标签（可选）。
- Campus 引用格式：`文档名 + 段落号 + 80字片段`。

4. Sources
- 结构：健康统计/连接卡/同步任务流/凭证告警/数据质量提示。
- 仅单源重试，不支持一键全重试。
- 支持失败诊断展开与重认证跳转，问题可联动到 Schedule。

5. Profile
- 分组：学业背景/计划偏好/隐私声明/保存反馈。
- 新增 `GPA` 字段。
- 保留字段影响说明（解释对 Assistant 的作用）。

## 接口与类型冻结
- 扩展：`ChatMessage.status/streamId/activeTrace`，`ApprovalAction` 增加会话关联与执行态。
- 新增接口：
- `GET /api/v1/schedule/events`
- `POST /api/v1/assistant/conversations/{id}/messages/stream`（SSE）
- `PATCH /api/v1/assistant/approvals/{id}`
- SSE 事件固定：`message.started/message.delta/trace.delta/approval.proposed/message.completed/message.error`。

## 并发与不卡死保障（独立章节）
- 交互锁范围：只锁“当前按钮”，禁止全页锁定。
- 慢请求策略：超过阈值（建议 8s）自动转后台任务，页面可继续操作。
- 取消能力：长请求/任务必须提供 Cancel。
- 状态释放：所有异步流程必须 `try/finally` 释放 pending，避免僵死按钮。
- 主线程保护：禁止在 UI 线程做重计算；重任务下沉后端或 Worker。
- 并发控制：同一资源去重请求（防连点重复提交），不同资源可并行。
- 可观测性：统一上报超时、取消、重试、失败码与耗时分位数。
- 降级与恢复：网络抖动时保留可交互 UI，失败后提供重试且不丢上下文。
- 前端验收红线：任一 API 超时/失败时，页面其余按钮仍可操作，不允许“点哪里都没反应”。

## 企业级数据加载与存储模式（新增）

- 三层职责固定：
- `API Client`：只负责请求、鉴权头、错误归一化，不做页面触发时机判断。
- `Query/Server State Layer`：负责 query key、缓存、去重、失效、重试。
- `UI Layer`：组件只消费状态，统一由 query 层驱动；遗留请求通道已清理，不再保留组件级直连入口。
- 统一 query key（按 `userId` 作用域）：
- `profile`
- `academicSnapshot`
- `scheduleToday`
- `sources`
- 统一 stale 策略：
- `profile`: 30 分钟
- `academicSnapshot`: 5 分钟
- `scheduleToday`: 2 分钟
- `sources`: 1 分钟
- 失效矩阵：
- 登录进入应用：触发一次会话级预取（读取缓存优先），后续统一走 query 层。
- `/sources` 手动 `sync/all` 成功：仅失效 `academicSnapshot`、`scheduleToday`、`sources`，再定向刷新。
- Profile 保存：仅失效 `profile`，不触发 schedule 重拉。
- 页面切换：只读缓存，不新增页面级重复请求，页面级直连入口不再保留。
- 明确禁止：
- 禁止同一份数据在多个组件各自维护请求入口。
- 禁止组件级 `onMounted(fetchXxx)` 作为主加载模式。

## Test Plan
1. 路由与职责
- 5 页可达，Dashboard 无重操作，所有摘要 1 跳转到处理页。

2. 核心业务闭环
- Assistant 审批仅消息内，Approve 后立即执行并回写状态。
- Sources 可诊断并单源重试；Profile 保存后可影响个性化建议。

3. 并发稳定性
- 任一长请求不阻塞全页交互。
- 后台任务可取消、可重试、可追踪。
- 连续点击/网络慢/接口超时场景下无全局卡死。

## 9. 自动为主 + 手动兜底（2026-04-04）

### 9.1 数据分层（不改后端）
- 重操作层：`POST /api/v1/sync/all`、`POST /api/v1/bb/courses`、`POST /api/v1/tis/info`。
- 轻读取层：`bb/calendar`、`bb/grades`、`bb/files`、`tis/schedule`、`tis/grade`、`tis/credit`。
- UI 层：只消费 `useWorkspaceStore` 的 query/state，不在页面组件里直接发请求。

### 9.2 自动同步编排器
- 前端新增 `autoSyncMeta`：`autoSyncState`、`lastAutoSyncAt`、`nextAutoSyncAllowedAt`、`autoSyncFailureCount`、`lastAutoSyncError`。
- `maybeAutoSync(reason)` 触发条件：CAS 登录、当前无进行中的 sync、已过冷却/退避窗口、快照硬过期（6 小时）或首次无快照。
- 成功后仅失效并刷新：`academicSnapshot`、`scheduleToday`、`sources`。
- 失败后指数退避：`1m / 5m / 15m / 30m`。

### 9.3 触发矩阵
- 登录进入应用：延迟后台尝试一次自动同步，不阻塞首屏。
- 应用回前台（focus）与网络恢复（online）：按条件尝试自动同步。
- 手动 `/sources -> Sync All Sources`：始终保留，作为强制刷新与故障恢复入口。

### 9.4 重字段低频刷新
- `bbCourseCount` 与 `tis/info` 按 24 小时低频刷新。
- 在 `Profile` / `Sources` 页面进入时做按需检查；未到时效直接读缓存。
- 重字段允许显示未知（例如 `bbCourseCount: null` 显示 `-`），避免为展示而高频重抓。

## 10. Profile Identity Card 模式（2026-04-04）

- 本轮将 Profile 右侧身份区升级为 `Identity Card`，统一展示 `users` 业务字段（不含 `created_at/updated_at`）：
- `user_id, name, pinyin_name, photo, gender, birth_date, college, dormitory, phone, email, gpa, rank, department, interest`
- UI 展示层按产品要求隐藏 `pinyin_name`，其余字段按配置渲染。
- 前端 canonical 数据结构：`IdentityCardData`（统一真相源：`useWorkspaceStore().identityCard`）。
- 数据来源按分层合并：
- session：`user_id, name, email`
- `POST /api/v1/tis/info`：`name/pinyin_name/gender/birth_date/college/department/dormitory/phone/email/interest`（可用即覆盖，已由 `GET /api/v1/user/profile` 聚合替代直连）
- `GET /api/v1/tis/grade`：`gpa/rank`
- `POST /api/v1/tis/photo`：`photo`（仅展示，不上传写库）
- 后端持久化：`interest` 通过 `GET/POST/PATCH/DELETE /api/v1/user/interest` 读写；Profile 页提供 Interests 编辑区与 Save 按钮
- 字段显示规则：空值统一显示 `-`；`birth_date` 前端格式化为 `YYYY-MM-DD`，非法值回退 `-`。
- `interest` 为本轮唯一可编辑 identity 字段；其余 identity 字段保持展示态。
- 仍遵循统一数据层约束：组件不新增 `onMounted` 直连请求，Identity 读取由会话级预取与 query 层驱动。

## 11. 全局字体规范（Apple 风格）

- 前端全局字体统一使用 Apple 风格系统字栈（`--font-sans`）：
- `"SF Pro Display", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Helvetica Neue", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", "Segoe UI", sans-serif`
- 禁止在业务页面新增与该字栈冲突的页面级字体覆盖。
- `theme-mono` 不再覆盖 `--font-sans`，避免切换主题后破坏全局字体一致性。

## 12. Identity Header Layout Update (2026-04-05)

- Identity header uses a two-column fill layout on desktop: left is photo + name + student ID, right is compact identity fields.
- Right-side header fields are `name`, `student ID`, and `department`; `college` and `email` are moved back to the lower field grid.
- Photo is enlarged and rendered without extra photo frame border, while keeping the same data source.
- Mobile layout automatically stacks into one column to avoid squeeze and overflow.

## 13. Assistant Markdown Rendering Update (2026-05-09)

- Assistant message rendering supports Markdown headings from `#` through `######`, GitHub-style pipe tables, table alignment markers, inline formatting inside table cells, and raw `<br>` line breaks emitted by the model.
