# Mail Frontend Integration

更新时间：2026-05-20

## 前端可见行为

- Sources 页面里的 Mail 卡片现在提供 `Log in mailbox` 按钮。
- 点击按钮会弹出邮箱登录窗口，用户需要填写 provider、邮箱地址和邮箱授权码/密码。
- 新增 `/mail` 页面，支持：
  - 查看当前邮箱登录状态
  - 登录或退出邮箱
  - 同步 `INBOX`
  - 查看已同步邮件列表
  - 打开邮件详情
  - 发送邮件

## 接口依赖

前端直接依赖现有后端接口：

- `GET /api/v1/mail/account`
- `POST /api/v1/mail/account/login`
- `POST /api/v1/mail/account/logout`
- `POST /api/v1/mail/sync`
- `GET /api/v1/mail/messages`
- `GET /api/v1/mail/messages/{mail_id}`
- `POST /api/v1/mail/send`

这些请求都需要当前应用登录态的 `Authorization` token。

## 已知限制

- 不支持多邮箱同时管理。
- 不支持附件。
- 不做草稿持久化。
- 不提供 mock 邮件数据；后端不可用时直接显示接口错误。
