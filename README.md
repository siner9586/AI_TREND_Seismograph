# AI 趋势脉冲 / AI Trend Seismograph

AI 趋势脉冲是一个面向 AI 研究、开源项目、数据集、Benchmark、机构动态和工程生态的趋势异常波动侦测 MVP。它不是新闻流，而是把论文、GitHub、关键词、方法、数据集、机构和 Watchlist 聚合成可解释的“趋势脉冲”。

## 产品价值

- 发现突然升温的研究方向、方法范式、数据集和 Benchmark。
- 识别 GitHub 项目的异常 star 增长和 topic 共振。
- 追踪机构在某一方向的密集发布。
- 标记冷门方向复活、多源共振和 Watchlist 命中。
- 以小时热点和每日报告双节奏持续积累趋势数据库。

## 架构

```text
arXiv / GitHub / optional APIs
        |
 Python pipeline: fetch -> extract -> match -> score -> report -> push
        |
 File data/*.json fallback  <->  Neon Postgres trend database
        |
 Astro static site + Cloudflare Pages Functions API
        |
 GitHub Actions schedule + optional Worker daily compensation
        |
 RSS / Telegram / Email / Webhook
```

生产模式只使用真实抓取数据。没有 Neon、Cloudflare 或 API Key 时，系统会自动降级到本地文件模式；不会用 mock 数据冒充生产趋势。

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install

python -m trend_seismograph run-hourly --hour 2026-06-13T10 --storage=file --dry-run=false
python -m trend_seismograph qa-hourly --hour 2026-06-13T10
npm run build
```

## CLI

```bash
python -m trend_seismograph run-hourly --hour 2026-06-13T10
python -m trend_seismograph run-daily --date 2026-06-13
python -m trend_seismograph qa-hourly --hour 2026-06-13T10
python -m trend_seismograph qa --date 2026-06-13
python -m trend_seismograph push-hotspots --hour 2026-06-13T10
```

通用参数：`--dry-run`、`--force`、`--no-push`、`--storage=file|neon|both`、`--source=arxiv,github,openalex`。

## 小时热点

输出：

- `data/hotspots/YYYY-MM-DD/HH.json`
- `data/hotspots/latest.json`
- `data/hotspots/index.json`

小时热点包含扫描规模、最高震级、Top hotspots、Watchlist 命中、GitHub surges、方法/数据集/机构信号、source status、partial、caveats 和确定性自然语言总结。

## 重点总结与展示规则

最新热点不接大模型，采用确定性自然语言总结器：`src/trend_seismograph/reports/curation.py`。

每个热点应生成并展示：

- `curated_summary`：抓取目标全文总结。它不是短字段拼接，而是一段自然语言解读，说明抓到了哪些代表目标、这些目标共同说明什么、工程侧/研究侧/机构账号侧各有什么重点，以及判断边界在哪里。
- `signal_takeaways`：总体归纳结论。它归纳多个抓取目标的总体意义，覆盖总体判断、内容重点、工程侧归纳、研究侧归纳、机构账号归纳、证据链归纳和观察建议。
- `source_link_groups`：分组信号链接。
- `evidence_digest`：证据摘要。
- `signal_focus`：主导来源、代表目标与核心信号字段。

前端详实卡片由 `web/src/components/TrendCard.astro` 统一渲染，旧数据缺少这些字段时会自动 fallback。详细规则见 `docs/site-style-rules.md`。

## 共现网络图规则

`/graph/` 的关键词共现网络必须保持当前中文顶刊论文机制图风格：白底、克制配色、四层分区、节点卡片、柔和弧线、图例、窗口信息、图形读法和中心节点说明。实现文件：`web/src/components/CooccurrenceGraphLite.astro`。

## GitHub Actions

- `.github/workflows/ci.yml`：lint、tests、TypeScript check、Astro build、schema/env validate。
- `.github/workflows/hourly-hotspots.yml`：每 2 小时刷新一次小时热点，可手动触发。
- `.github/workflows/daily-trend-seismograph.yml`：日报生成，可手动触发。

Cloudflare 与 Actions 通过文件存在检查、KV lock 和 push dedupe 避免互相覆盖或重复推送。

## Cloudflare Pages

构建命令：

```bash
npm install
npm run build
```

发布目录：`web/dist`。Pages Functions 位于 `functions/api`，API 默认查询 Neon，失败时读取静态 JSON asset。

## 站点页面

- `/` 首页仪表盘
- `/hotspots` 小时热点
- `/reports/YYYY-MM-DD` 日报
- `/archive` 归档
- `/trends/[topic]` 趋势详情
- `/institutions` 机构统计
- `/github` GitHub 趋势
- `/graph` 关键词共现
- `/watchlist` Watchlist
- `/sources` 数据源说明

## QA 与测试

```bash
pytest
python -m trend_seismograph qa-hourly --hour 2026-06-13T10
python -m trend_seismograph qa --date 2026-06-13
npm run build
```

QA 检查日报、Markdown、latest 指针、小时 latest、evidence、source_url、magnitude、severity、source_status、mock 标记、文件 fallback 和推送去重。

## 局限性

- arXiv affiliation 不稳定，机构识别以词典和可用 metadata 为主。
- GitHub star 增量需要先积累 snapshot，首次运行不会判定 star 暴涨。
- OpenAlex 和 Semantic Scholar 在 MVP 中是可选增强源。
- 历史不足 30 天时，趋势判断会标记低历史置信度。
