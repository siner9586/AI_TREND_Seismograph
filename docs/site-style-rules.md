# AI 趋势脉冲站点样式与内容规则

本文件用于约束站点后续每次自动更新与人工修改的展示规则，避免页面风格、术语和热点总结口径反复漂移。

## 1. 命名规则

- 站点中文名称统一为：AI 趋势脉冲。
- 站点可保留英文工程名 `AI Trend Seismograph` 用于仓库名、脚注或历史兼容。
- 面向用户的中文页面、导航、页面 title、首页 h1、归档页、日报页、趋势详情页、GitHub 页、机构页、数据源页、Watchlist 页统一使用“AI 趋势脉冲”。

## 2. 最新热点总结规则

最新热点卡片必须采用“确定性规则总结”，不调用大模型。总结器以结构化字段为依据，核心字段包括：

- `metrics.paper_count`
- `metrics.repo_count`
- `metrics.github_star_delta`
- `metrics.method_mentions`
- `metrics.dataset_mentions`
- `metrics.institution_mentions`
- `related_methods`
- `related_datasets`
- `related_institutions`
- `suggested_watch_keywords`
- `evidence`
- `source_urls`
- `caveats`
- `confidence`

每个热点应输出以下展示层字段：

- `curated_summary`：一段结构化摘要，说明该热点是什么、信号来自哪里、为什么值得观察。
- `signal_takeaways`：3 至 7 条重点结论，覆盖来源结构、开源热度、方法线索、机构/账号线索、证据链和边界提示。
- `source_link_groups`：按“代表项目、论文来源、方法与数据集信号、其他信号”分组的来源链接。
- `evidence_digest`：对代表性证据给出“为什么纳入”的短说明。
- `signal_focus`：用于前端解释的主导来源、核心方法、机构线索和计数字段。

前端卡片必须优先展示数据层生成的 `curated_summary`、`signal_takeaways`、`source_link_groups` 和 `evidence_digest`。如果旧数据尚未包含这些字段，前端必须根据现有字段自动生成 fallback，不允许出现空白卡片。

## 3. 热点卡片展示结构

详实热点卡片按以下顺序展示：

1. 主题、标签与震级。
2. 原始摘要 `summary`。
3. “抓取内容重点”：优先显示 `curated_summary`，并注明“确定性规则总结 · 不调用大模型”。
4. “重点结论”：显示 `signal_takeaways` 或 fallback 结论。
5. “信号解释”：显示主导来源、相关方法、数据集/Benchmark、相关机构/账号、命中关键词和后续观察词。
6. 计算摘要 `calculation_summary`。
7. caveats 边界提示。
8. 证据摘要 `evidence_digest`。
9. 代表性信号 `evidence`。
10. 分组信号链接。

## 4. 共现网络图规则

`/graph/` 页共现网络图必须保持中文顶刊论文机制图质感：

- 白底、克制配色、低饱和色系。
- 采用“核心议题层、方法工具层、数据基准层、语义关键词层”四分区结构。
- 节点以卡片式模块展示，包含节点名称、节点类型和频次。
- 边使用柔和弧线，边越粗代表共现强度越高。
- 必须显示图例、窗口信息、图形读法和当前中心节点。
- 重复节点必须在前端合并，例如 `RAG/rag`、`MCP/mcp`、`Agents/agents` 不应在视觉上造成明显重复混乱。
- 不使用商业海报感、科技炫光感、过强渐变和过度装饰。

## 5. 维护原则

- 更新流水线时，优先保持数据字段稳定，前端只负责呈现和兜底。
- 不接大模型时，所有总结必须可解释、可复现、可从 JSON 字段追溯。
- 新增页面必须复用全局样式变量和现有卡片规范。
- 每次修改后应检查面向用户页面命名是否统一为“AI 趋势脉冲”。
