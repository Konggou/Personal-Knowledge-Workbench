# V6-1 后续实施拆分

当前状态：V6-1 已完成，以下内容作为归档记录与后续拆分参考。

## V6-1A 代码低风险去冗余

- 抽取前端重复 helper：
  - 文件类型校验
  - 来源错误归一化
  - 来源预览上下文格式化
- 删除后端无调用死代码：
  - `SourceService._fetch_web_content`
- 当前状态：
  - 已完成
- 验证：
  - `apps/web` typecheck 已通过
  - 后端 `tests/backend/test_agentic_v3.py` 已通过
  - `project-chat-client` 定向 `vitest` 已通过

## V6-1B 文档统一修正

- 修正真相文档与实现冲突：
  - 仅保留统一图编排运行时
  - 不再暗示 `v2` 回退路径存在
- 同步计划/进度：
  - 标记 V6-1 已启动
  - 记录“先去高置信冗余，再做结构级收敛”
- 当前状态：
  - 运行时残留已清理
  - 主文档中的 `V4/V5` 阶段标题残留已改为当前状态表述

## V6-1C 结构级重复逻辑收敛

- 前端：
  - `project-chat-client.tsx` 中 session/source 刷新和 optimistic update 合流
- 后端：
  - `SessionService` sync/stream 公共步骤抽取
  - 检索/生成链路中的 diagnostics/evidence 组装整理
- 约束：
  - 不改公开 API
  - 不改前台术语
  - 先补测试再收敛逻辑
- 当前状态：
  - 后端 `SessionService` 公共步骤抽取已完成
  - 已补 `/api/v1/sessions/{session_id}/messages/stream` 的外部证据流式回归测试
  - 前端聊天页已合并重复的项目视图刷新逻辑
  - 前端聊天页已合并流式消息事件中的重复状态更新逻辑
  - 更深一层的 optimistic update 合流与检索/生成链路整理转入后续批次
