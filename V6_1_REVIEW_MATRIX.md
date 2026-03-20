# V6-1 冗余审查清单

## Frontend

| 模块 | 冗余类型 | 证据位置 | 建议动作 | 优先级 | 可直接实施 |
| --- | --- | --- | --- | --- | --- |
| 路由与页面装配 | 页面入口以数据装配为主，未见明显重复获取链路 | `apps/web/src/app/projects/[projectId]/page.tsx`, `apps/web/src/app/knowledge/page.tsx` | 保持当前薄页面策略，暂不改 | P3 | 否 |
| 聊天主区 | 会话刷新、来源刷新、optimistic update 仍有模块内重复片段 | `apps/web/src/components/projects/project-chat-client.tsx` | 划入 `V6-1C`，抽公共刷新/更新 helper | P2 | 否 |
| 壳层与知识库/项目页 | 文件类型校验、来源错误归一化、来源预览上下文格式化重复实现 | `apps/web/src/components/projects/project-chat-client.tsx`, `apps/web/src/components/knowledge/knowledge-page-client.tsx` | 抽到共享 `lib/source-utils.ts` | P1 | 是 |
| 会话/工作台交互 | 删除、重命名、搜索跳转模式相似但仍承载各自页面语义 | `apps/web/src/components/workspace/workspace-page-client.tsx`, `apps/web/src/components/sessions/sessions-page-client.tsx` | 暂不合并，避免过度抽象 | P3 | 否 |
| API 封装 | `lib/api.ts` 里请求模式相似但接口清晰，暂未形成高价值冗余 | `apps/web/src/lib/api.ts` | 记录为观察项，不在第一批改 | P3 | 否 |

## Backend

| 模块 | 冗余类型 | 证据位置 | 建议动作 | 优先级 | 可直接实施 |
| --- | --- | --- | --- | --- | --- |
| 路由层 | 仍保持薄路由，404/422 处理集中在 service，未见明显重复问题 | `apps/api/app/api/routes/*` | 保持现状 | P3 | 否 |
| SessionService | 普通发送与流式发送的状态写入、答案生成前步骤仍有重复 | `apps/api/app/services/session_service.py` | 划入 `V6-1C`，后续抽公共消息发送步骤 | P2 | 否 |
| SourceService | 存在未使用的网页抓取 helper | `apps/api/app/services/source_service.py` | 删除死代码 `_fetch_web_content` | P1 | 是 |
| 检索与生成 | diagnostics 组装和 evidence 融合仍偏长，但与当前行为强绑定 | `agent_orchestrator_service.py`, `grounded_generation_service.py`, `search_service.py` | 保持行为优先，后续再做结构收敛 | P2 | 否 |
| 文档层 | `V4/V5` 阶段标题残留会让读者误以为这些章节仍按旧版本语义维护 | `README.md`, `BACKEND_STRUCTURE.md`, `IMPLEMENTATION_PLAN.md`, `TECH_STACK.md` | 统一改为描述当前状态的标题，避免版本残留 | P1 | 是 |
| 仓储/DTO 转换 | repository -> summary 的重复转换存在但边界清晰 | `project_repository.py`, `session_repository.py`, `source_repository.py` | 暂不统一抽象，避免扩大改动面 | P3 | 否 |

## 结论

- 第一批已执行项应聚焦：
  - 前端共享 helper 去重
  - 后端死代码删除
  - 文档事实冲突修正
- 第二批保留给结构级收敛：
  - 聊天主区刷新/optimistic update 合流
  - `SessionService` sync/stream 公共步骤抽取
  - 检索与生成链路中的 diagnostics/evidence 组装整理
