# Assistant 后端接入执行计划

更新时间：2026-04-10  
适用范围：`frontend/**`  
目标：把当前 `Assistant` 页面从本地 mock 迁到后端真实 `chat/* + history/*` 链路，同时保证 UI 与后端能力一致。

## 1. 任务冻结

### 1.1 本轮目标

- `Assistant` 页面直接接入现有后端真实接口：
- `POST /api/v1/chat/create_session`
- `POST /api/v1/chat/chat_on_docs?session_id=...&deep_think=...`
- `GET /api/v1/history/get_sessions`
- `GET /api/v1/history/get_messages?session_id=...`
- `Assistant` 页面允许空会话直接发消息，体验对齐普通 AI 聊天窗口。
- 保留原模型选择器位置，但只允许切换：
- `DeepSeek Chat`
- `DeepSeek R1`
- 删除模式选择器。
- 保留审批 / trace / 多知识库相关 UI，但统一展示为“未接入 / 不可用”，且不可触发真实请求。

### 1.2 非目标

- 本轮不接 `Study`。
- 本轮不删除 `Study` 页面，只记录为后续工作。
- 本轮不接 `Profile interest` 等 `Profile` 真实接口。
- 本轮不改任何 `backend/**` 代码。
- 本轮不新增新的后端契约，只向现有接口妥协。

## 2. ADR

### 2.1 决策

采用“混合方案 C”：  
不新建独立 Assistant store，但也不直接把整个 `useWorkspaceStore` 粗暴替换；而是在现有 store 内引入 Assistant remote 子状态与协议适配层，按 Gate 顺序逐步切换真实链路。

### 2.2 决策驱动

- 必须尽快把 `Assistant` 主链路接到真实后端，而不是继续维护 mock。
- 必须删除与后端不一致的模式语义，并把模型切换收缩成后端真实支持的 `DeepSeek Chat / DeepSeek R1` 双态。
- 必须把 SSE、会话真相源、刷新恢复这些高风险点先收束，再改页面。

### 2.3 方案对比

| 方案 | 改动面 | 回归风险 | 开发时长 | 回退成本 | 与后端契约一致性 | 结论 |
|---|---|---:|---:|---:|---:|---|
| A. 直接在现有 `useWorkspaceStore` 上硬改 | 小 | 高 | 短 | 高 | 中 | 太快，但容易把协议迁移和全局状态重构绑死 |
| B. 新建 Assistant 专用 store/类型 | 大 | 中 | 长 | 中 | 高 | 结构最干净，但本轮成本过高 |
| C. 现有 store 内新增 Assistant remote 子状态与适配层 | 中 | 中 | 中 | 低 | 高 | 最平衡，适合本轮 |

### 2.4 选择 C 的原因

- 比 A 稳：不会把 SSE 生命周期和全局多域状态直接缠死。
- 比 B 快：不需要本轮重构整套状态架构。
- 允许按 Gate 回退：每一层都能独立验证，不用一次性推翻现有页面。

## 3. 设计原则

1. 真实优先：UI 只表达后端现在真的有的能力。
2. 体验优先：用户进入页面后可像普通 AI 聊天窗口一样直接提问。
3. 协议先行：先冻结 SSE 和会话映射规则，再改状态层和视图层。
4. 小步回退：每一 Gate 都要可单独验证、可单独停下。
5. 范围硬冻结：本轮只做 `Assistant` 主链路，不顺手扩展到 `Study` 或 `Profile`。
6. 模型语义收缩：前端不再暴露抽象模型系统，只暴露后端真实支持的两个 DeepSeek 通道。

## 4. 真实后端协议冻结

## 4.1 会话创建

- 接口：`POST /api/v1/chat/create_session`
- 用途：创建远端会话
- 响应真相源：`session_id`
- 规则：
- `session_id` 是远端唯一真相源
- 前端本地 `conversation.id` 只做 UI key，不反向驱动远端

## 4.2 会话列表

- 接口：`GET /api/v1/history/get_sessions`
- 用途：页面初始化、刷新恢复、会话列表回放
- 关键字段：
- `session_id`
- `session_name`
- `created_at`
- `updated_at`

## 4.3 消息历史

- 接口：`GET /api/v1/history/get_messages?session_id=...`
- 用途：切换会话时回放历史
- 关键字段：
- `message_id`
- `user_question`
- `model_answer`
- `documents`
- `recommended_questions`
- `think`
- `created_at`

## 4.4 流式聊天

- 接口：`POST /api/v1/chat/chat_on_docs?session_id=...&deep_think=...`
- 事件：
- `message`
- `end`
- `error`

### 模型切换与后端映射

- 前端模型选择器只保留两个选项：
- `DeepSeek Chat`
- `DeepSeek R1`
- 请求映射规则：
- `DeepSeek Chat` -> `deep_think=false` -> 后端使用 `deepseek-chat`
- `DeepSeek R1` -> `deep_think=true` -> 后端使用 `deepseek-reasoner`
- 这不是通用模型系统，不再保留 GPT / Claude / Gemini 语义。

### `message` 事件 payload 分三类

1. 文档上下文：

```json
{ "documents": [] }
```

2. 模型输出增量：

```json
{ "role": "assistant", "content": "token chunk", "thinking": false }
```

3. 推荐问题：

```json
{ "recommended_questions": ["..."] }
```

### `end` 事件

- 形态：`data: [DONE]`
- 规则：表示当前 assistant 消息流结束

### `error` 事件

- 规则：
- 保留已经收到的 assistant 内容
- 当前消息标记为失败态或追加系统错误提示
- 输入框保持可继续发消息

### `thinking` 字段处理

- 当后端返回 `thinking: true` 时，说明当前 chunk 来自推理内容，主要出现在 `DeepSeek R1`
- 本轮计划要求：
- 不把它映射为旧的 trace 系统
- 将其作为 R1 专属“thinking stream”独立渲染，或作为 assistant 消息内的次级区域渲染
- 它必须和主回答 chunk 分开拼接，不能污染最终 `model_answer` 正文展示区域

## 5. 文件级执行顺序

## Gate 1: 协议层冻结

目标：先明确 Assistant 主链路的 DTO、SSE 事件矩阵、DeepSeek 双模型切换规则。

涉及文件：

- [frontend/composables/useApiClient.ts](D:/26Spring/SE/team-project-26spring-26s-4/frontend/composables/useApiClient.ts)
- [frontend/types/app.ts](D:/26Spring/SE/team-project-26spring-26s-4/frontend/types/app.ts)
- [docs/frontend-backend-api.md](D:/26Spring/SE/team-project-26spring-26s-4/docs/frontend-backend-api.md)

完成标准：

- 会话 DTO、消息 DTO、SSE chunk DTO 都有明确前端定义
- `DeepSeek Chat / DeepSeek R1` 与 `deep_think=false|true` 的映射规则写清楚
- `message/end/error` 的前端收口规则写清楚
- 没有再依赖虚构的 `/assistant/*`

Gate 通过条件：

- API 映射文档和类型定义能覆盖现有后端真实返回

## Gate 2: API 层计划

目标：在 `useApiClient` 增加四个真实方法，不动页面。

涉及文件：

- [frontend/composables/useApiClient.ts](D:/26Spring/SE/team-project-26spring-26s-4/frontend/composables/useApiClient.ts)

新增方法：

- `createChatSession`
- `listChatSessions`
- `listChatMessages`
- `streamChatOnDocs`

额外要求：

- `streamChatOnDocs` 必须先完成 SSE parser 设计
- parser 必须能区分三种 `message` payload
- `streamChatOnDocs` 必须支持 `deepThink: boolean` 或等价字段
- API 层不直接负责 UI 逻辑

Gate 通过条件：

- 四个方法签名、返回 DTO、错误归一化策略都明确
- SSE parser 行为可单测或最少可独立手测

## Gate 3: 状态层计划

目标：把 `Assistant` 主链路切到真实后端，但不扩散影响其他模块。

涉及文件：

- [frontend/composables/useWorkspaceStore.ts](D:/26Spring/SE/team-project-26spring-26s-4/frontend/composables/useWorkspaceStore.ts)

必须落实的规则：

- 增加 Assistant remote 子状态，不把全局状态粗暴重写
- `backendSessionId` 或等价字段是远端真相源
- hydration 必须有单次锁
- 首发消息与建会话之间必须原子化，避免并发创建重复会话
- 切换会话时拉取远端消息历史
- `sendMessage` 改成真实 SSE 拼接，不再生成 mock 回复
- 运行时模型状态只保留两档：`deepseek-chat` / `deepseek-reasoner`

错误收口规则：

- `end` 之前收到的 assistant delta 必须拼到同一条 assistant 消息
- `thinking: true` 的 chunk 必须进入独立 thinking 缓冲区
- `error` 时保留已有 delta
- 失败后会话切换、重新发送、输入框都不能锁死

本地存储兼容策略：

- 旧本地 `assistant-conversations` 数据不再作为真相源
- 若结构不兼容，直接失效并以远端会话重建
- 本地只允许保留 UI 级辅助状态，不保存伪历史

Gate 通过条件：

- 远端 session 与本地 conversation 绑定规则明确
- 首发消息、刷新恢复、切换会话三条路径都能解释清楚

## Gate 4: 视图层计划

目标：让页面表达真实能力，删掉错误语义。

涉及文件：

- [frontend/pages/assistant/index.vue](D:/26Spring/SE/team-project-26spring-26s-4/frontend/pages/assistant/index.vue)

必须改动：

- 保留原模型选择器位置，但仅展示 `DeepSeek Chat` / `DeepSeek R1`
- 删除模式选择器
- 输入框、发送按钮、会话列表、消息区切换到真实数据流
- 空会话允许直接发消息

保留但禁用：

- 审批 UI
- trace UI
- 多知识库 UI

禁用要求：

- 统一文案：`Unavailable` / `Not Integrated`
- 统一不可触发真实请求
- 禁用态视觉和交互一致

Gate 通过条件：

- 页面上只保留 `DeepSeek Chat / DeepSeek R1` 两档模型切换，不再出现其他模型或模式分流控件
- 保留区块不会误导用户以为可用

## Gate 5: 类型与无效逻辑清理

目标：只清理本轮已经确认废弃的运行时依赖。

涉及文件：

- [frontend/types/app.ts](D:/26Spring/SE/team-project-26spring-26s-4/frontend/types/app.ts)
- [frontend/composables/useWorkspaceStore.ts](D:/26Spring/SE/team-project-26spring-26s-4/frontend/composables/useWorkspaceStore.ts)

清理原则：

- 先删除模式语义依赖，再把模型语义收缩到 DeepSeek 双档
- 不一次性删干净所有历史类型
- 只删除已确定不会再走的运行时入口

删除条件：

- 新主链路已稳定跑通
- 页面已不再引用旧模式逻辑，且模型选择器只引用 DeepSeek 双档逻辑

## Gate 6: 文档更新

涉及文件：

- [docs/frontend-backend-api.md](D:/26Spring/SE/team-project-26spring-26s-4/docs/frontend-backend-api.md)
- [docs/frontend-api-gap.md](D:/26Spring/SE/team-project-26spring-26s-4/docs/frontend-api-gap.md)
- [docs/frontend-backend-api-requirements.md](D:/26Spring/SE/team-project-26spring-26s-4/docs/frontend-backend-api-requirements.md)

更新内容：

- 标记 Assistant 主链路已接到 `chat/* + history/*`
- 标记模型切换真实映射为 `deep_think=false|true`
- 明确未接入部分仍是审批 / trace / 多知识库标准化接口
- 联调端口继续写 `9000`

## 6. 验收用例

## 用例 1：首次进入 Assistant，无会话直接发消息

- 前置：
- 已登录
- 后端可访问
- 操作：
- 打开 `/assistant`
- 在空页面直接输入一条消息并发送
- 期望 UI：
- 自动创建会话
- 用户消息立即出现
- assistant 消息按流式逐步更新
- 期望网络：
- 先 `POST /api/v1/chat/create_session`
- 再 `POST /api/v1/chat/chat_on_docs?session_id=...&deep_think=false`
- 失败定义：
- 发送后无任何消息出现
- 创建了多个重复会话
- SSE 结束前 assistant 内容被拆成多条碎消息

## 用例 1B：切换到 DeepSeek R1 后发送消息

- 前置：
- 已登录
- 已进入 `Assistant`
- 操作：
- 在原模型选择器位置切到 `DeepSeek R1`
- 发送一条消息
- 期望 UI：
- 模型切换成功
- R1 的 thinking 内容与最终回答分区展示或独立展示
- 期望网络：
- `POST /api/v1/chat/chat_on_docs?session_id=...&deep_think=true`
- 失败定义：
- 切到 R1 后仍发送 `deep_think=false`
- thinking chunk 混入最终正文
- 切换模型后页面仍显示旧的 GPT / Claude / Gemini 选项

## 用例 2：刷新页面后恢复会话列表与历史

- 前置：
- 后端已存在至少一个会话和若干消息
- 操作：
- 打开 `/assistant`
- 刷新浏览器
- 期望 UI：
- 会话列表来自后端
- 选中会话后历史消息正确回放
- 期望网络：
- `GET /api/v1/history/get_sessions`
- `GET /api/v1/history/get_messages?session_id=...`
- 失败定义：
- 刷新后只剩本地 mock
- 会话标题或历史明显与后端不一致

## 用例 3：切换会话

- 前置：
- 至少两个远端会话
- 操作：
- 在左侧切换会话
- 期望 UI：
- 消息区切换为对应会话的历史
- 不混入其他会话消息
- 失败定义：
- 会话错绑
- 切换后消息区仍显示旧会话

## 用例 4：SSE error 收口

- 前置：
- 人为制造后端流式中断或请求异常
- 操作：
- 发送消息
- 期望 UI：
- 已收到的 assistant 内容保留
- 当前轮次出现明确失败提示
- 输入框仍可继续发送
- 失败定义：
- 页面卡死
- assistant 消息整条消失
- 发送按钮永久不可用

## 用例 5：未接入 UI 禁用

- 操作：
- 打开审批、trace、多知识库相关区域
- 期望 UI：
- 显示未接入/不可用
- 不发起真实请求
- 失败定义：
- 仍然触发 `/assistant/*` 或知识库占位请求
- 看起来可用但点了报错

## 用例 6：模型切换只剩 DeepSeek 双档

- 操作：
- 打开 `Assistant` 输入区底部原模型选择器位置
- 期望 UI：
- 只出现 `DeepSeek Chat` 和 `DeepSeek R1`
- 不再出现 GPT / Claude / Gemini
- 不再出现模式选择器
- 失败定义：
- 仍有旧模型选项
- 模型切换不在原位置
- 模式选择器仍存在

## 7. 风险与回退规则

## 风险 1：SSE 解析错乱

- 触发条件：
- assistant 回复被拆成多条碎消息
- `documents` / `recommended_questions` 被当成正文渲染
- 检测信号：
- 单次消息发送出现多个 assistant 主消息泡泡
- 处置动作：
- 先冻结页面改动，单独修复 SSE parser
- 回退触发线：
- 连续两条核心用例消息都发生错拼，立即回切旧 `sendMessage`

## 风险 2：会话错绑

- 触发条件：
- 当前 UI 会话与后端 `session_id` 不一致
- 检测信号：
- 切换会话后读到错误历史
- 处置动作：
- 立即核对 `backendSessionId` 绑定规则
- 回退触发线：
- 首发消息和切换会话任一主链路出现错绑，暂停后续 UI 清理

## 风险 3：首发消息并发导致重复建会话

- 触发条件：
- 空会话连续点击发送或 hydration 与 create_session 并发
- 检测信号：
- 后端短时间内生成多个新 session
- 处置动作：
- 增加 create-session 单次锁 / promise 复用
- 回退触发线：
- 复现场景稳定出现重复 session，即停止推进页面层变更

## 风险 4：未接入 UI 误触发请求

- 触发条件：
- 点击审批 / trace / 多知识库区域仍发网络请求
- 检测信号：
- DevTools Network 出现不该有的 `/assistant/*` 或多知识库请求
- 处置动作：
- 统一 capability 开关和禁用组件入口
- 回退触发线：
- 任意禁用区块仍可触发请求，则不进入收尾阶段

## 风险 5：DeepSeek 切换与请求参数错配

- 触发条件：
- UI 选择的是一个模型，但请求发送了错误的 `deep_think` 值
- 检测信号：
- 切换到 `DeepSeek R1` 后网络仍是 `deep_think=false`
- 或切回 `DeepSeek Chat` 后仍是 `deep_think=true`
- 处置动作：
- 立即把模型状态收束为布尔语义适配层，禁止继续透传旧 `AssistantModel` 集合
- 回退触发线：
- DeepSeek 两档切换任一方向错配可稳定复现，则不进入类型清理阶段

## 8. 执行完成判定

只有同时满足以下条件，才算本计划可进入 execute：

- Gate 1 到 Gate 6 都有明确负责人和变更文件
- 七个验收用例都可执行且有清晰失败定义
- 风险触发线和回退动作明确
- 计划范围没有漂移到 `Study` / `Profile` / `backend`
