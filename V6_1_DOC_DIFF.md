# V6-1 全量文档差异清单

| 文档 | 当前状态 | 需要统一的事实 | 优先级 |
| --- | --- | --- | --- |
| `BACKEND_STRUCTURE.md` | 已修正运行时仍可切换的旧叙述 | 保持“仅保留统一图编排运行时” | P1 |
| `IMPLEMENTATION_PLAN.md` | 已修正 `v2` 回退路径残留，但尚未记录 V6 第一项 | 新增 V6 第一项为“代码冗余审查与文档清理” | P1 |
| `progress.txt` | 已修正 runtime 残留，但仍停留在 V5/V4 视角 | 更新最后时间，并记录 V6-1 已启动与当前分批策略 | P1 |
| `PRD.md` | 产品事实与当前实现基本一致 | 继续作为产品事实基线，无需本批修改 | P2 |
| `APP_FLOW.md` | 主流程与当前路由一致 | 保持现状，后续仅在行为变化时更新 | P2 |
| `FRONTEND_GUIDELINES.md` | 设计规则与当前页面结构一致 | 保持现状 | P2 |
| `TECH_STACK.md` | 技术栈与路由/API 叙述一致 | 保持现状 | P2 |
| `AGENTS.md` | 执行入口和命名约束仍有效 | 保持现状 | P2 |
| `README.md` | 对外叙事与当前产品心智基本一致，但仍保留阶段性 `V4` 小节标题 | 已改为面向当前状态的“当前检索说明”表述 | P2 |

## 本批已直接修正

- 移除运行时可回退到 `v2` 的旧文案残留。
- 将 V6 第一项显式写入计划与进度文档，避免仓库状态继续停留在 V5 结论。
- 将 `README.md`、`BACKEND_STRUCTURE.md`、`IMPLEMENTATION_PLAN.md`、`TECH_STACK.md` 中残留的 `V4/V5` 阶段标题改成当前状态表述。

## 后续仍需跟踪

- 每次新的 V6 子批次完成后，同步更新：
  - `progress.txt`
  - `IMPLEMENTATION_PLAN.md`
  - 必要时更新 `README.md`
