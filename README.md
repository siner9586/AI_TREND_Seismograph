# AI 趋势地震仪 / AI Trend Seismograph

AI 趋势地震仪是一个面向 AI 研究、开源项目、数据集、Benchmark、机构动态和工程生态的趋势异常波动侦测 MVP。它不是新闻流，而是把论文、GitHub、关键词、方法、数据集、机构和 Watchlist 聚合成可解释的“趋势震级”。

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
 Cloudflare Worker Cron + KV locks -> trigger pipeline
        |
 RSS / Telegram / Email / Webhook
```

生产模式只使用真实抓取数据。没有 Neon、Cloudflare 或 API Key 时，系统会自动降级到本地文件模式；不会用 mock 数据冒充生产趋势。

## 本地运行

```bash
cd /Users/wangzheng/Documents/vibecoding/AI_TREND_Seismograph

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

npm install

python -m trend_seismograph run-hourly --hour 2026-06-13T10 --storage=file --dry-run=false
python -m trend_seismograph qa-hourly --hour 2026-06-13T10

python -m trend_seismograph run-daily --date 2026-06-13 --storage=file --dry-run=false
python -m trend_seismograph qa --date 2026-06-13

pytest
npm run build
```

## CLI

```bash
python -m trend_seismograph fetch --date 2026-06-13
python -m trend_seismograph fetch-hourly --hour 2026-06-13T10
python -m trend_seismograph analyze --date 2026-06-13 --lookback-hours 72
python -m trend_seismograph analyze-hourly --hour 2026-06-13T10
python -m trend_seismograph report --date 2026-06-13
python -m trend_seismograph run-hourly --hour 2026-06-13T10
python -m trend_seismograph run-daily --date 2026-06-13
python -m trend_seismograph sync-neon --date 2026-06-13
python -m trend_seismograph push-hotspots --hour 2026-06-13T10
python -m trend_seismograph qa --date 2026-06-13
python -m trend_seismograph qa-hourly --hour 2026-06-13T10
python -m trend_seismograph backfill --from 2026-06-01 --to 2026-06-13
```

通用参数：`--dry-run`、`--force`、`--no-push`、`--storage=file|neon|both`、`--source=arxiv,github,openalex`。

## 数据源

默认启用：

- arXiv API：`cs.AI`、`cs.LG`、`cs.CL`、`cs.CV`、`cs.RO`、`cs.IR`、`stat.ML`。
- GitHub REST Search API：无 token 可运行，配置 `GITHUB_TOKEN` 后速率更稳定。

可选增强：

- Semantic Scholar：配置 `SEMANTIC_SCHOLAR_API_KEY` 后可扩展。
- OpenAlex：配置 `OPENALEX_API_KEY` 后可扩展。

所有源保留 `source_url`，抓取失败不会阻断整体任务，失败状态写入 `source_status`。

## 小时级刷新

输出：

- `data/hotspots/YYYY-MM-DD/HH.json`
- `data/hotspots/latest.json`
- `data/hotspots/index.json`

小时热点包含扫描规模、最高震级、Top hotspots、Watchlist 命中、GitHub surges、方法/数据集/机构信号、source status、partial 和 caveats。

## 每日报告

输出：

- `data/reports/YYYY-MM-DD.json`
- `data/reports/YYYY-MM-DD.md`
- `data/latest.json`
- `data/history/index.json`

日报包含 24/72 小时异常、30 天基线、90/180 天背景、机构发布频率、方法和数据集异常、GitHub 增长、冷门复活、跨源共振和观察建议。

## 趋势震级算法

每个 topic 计算：

- `current_1h_count`、`current_24h_count`、`current_72h_count`、`current_7d_count`
- `baseline_daily_avg_30d`、`baseline_daily_std_30d`
- `growth_rate`、`z_score`、`burst_score`
- `source_diversity_score`、`cross_source_confirmation_score`
- `institution_concentration_score`、`github_signal_score`
- `dataset_signal_score`、`method_signal_score`、`cold_revival_score`

震级：

```text
M1.0-M2.0 微弱波动
M2.0-M3.0 局部升温
M3.0-M4.0 明显异常
M4.0-M5.0 疑似爆发
M5.0+ 强趋势震荡
```

每条趋势都包含 `calculation_summary`、`key_drivers`、`evidence`、`source_urls`、`caveats` 和 `confidence`。历史不足 30 天时会标记 `low_history_confidence=true`。

## Watchlist

配置文件：`config/watchlist.yml`。支持 topic、关键词、震级阈值、增长率阈值和推送开关。命中结果出现在首页、`/watchlist`、小时热点和日报 JSON 中。

## 推送

支持：

- RSS：总是生成 `data/rss.xml`
- Telegram：`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`
- Email：`SMTP_HOST`、`SMTP_USER`、`SMTP_PASS`
- Webhook：`PUSH_WEBHOOK_URL`

去重规则：`dedupe_key = event_type + topic + date + severity_label`，同一事件 24 小时内只推一次。文件模式记录在 `data/push_events.json`。

## Neon 配置

```bash
psql "$DATABASE_URL" -f db/migrations/001_init.sql
python scripts/seed_taxonomy.py
python -m trend_seismograph run-daily --date 2026-06-13 --storage=both
```

支持环境变量：`DATABASE_URL` 或 `NEON_DATABASE_URL`。Neon 不可用时，CLI 会保留文件输出，并把失败原因写入存储状态。

主要表：

- `sources`：数据源配置和权重。
- `raw_items`：论文、repo 等原始信号。
- `topics`、`item_topic_matches`：趋势 taxonomy 和匹配证据。
- `hourly_snapshots`：小时级趋势快照。
- `daily_reports`：每日报告索引。
- `repo_snapshots`：GitHub star 历史。
- `institutions`、`institution_topic_stats`：机构词典和机构-topic 统计。
- `watchlists`：关注方向配置。
- `push_events`：推送去重历史。

## Cloudflare Pages

构建命令：

```bash
npm install
npm run build
```

发布目录：`web/dist`。Pages Functions 位于 `functions/api`，API 默认查询 Neon，失败时读取静态 JSON asset。

## Cloudflare Worker Cron

Worker 目录：`workers/trend-cron-worker`。

```bash
cd workers/trend-cron-worker
npm install
npx wrangler dev --test-scheduled
npx wrangler deploy
```

Cron UTC 配置：

- 每小时第 8 分钟：`8 * * * *`
- 每日北京时间 06:18：`18 22 * * *`
- 补偿检查：`33,48 22 * * *`、`3,18,33,48 23 * * *`、`3,18,33,48 0 * * *`、`3,18,33,48 1 * * *`
- 每日北京时间 23:30 维护：`30 15 * * *`

Worker 使用 KV `TREND_LOCKS` 保存 `lock:hourly:YYYY-MM-DD-HH` 和 `lock:daily:YYYY-MM-DD`。触发方式优先 `PIPELINE_TRIGGER_URL`，否则通过 `GITHUB_TOKEN` + `GITHUB_REPOSITORY` 调用 GitHub Actions workflow_dispatch。

## API

Cloudflare Pages Functions：

- `GET /api/latest`
- `GET /api/hotspots/latest`
- `GET /api/reports/:date`
- `GET /api/topics`
- `GET /api/topics/:topic`
- `GET /api/topics/:topic/history?window=30d|90d|180d`
- `GET /api/github/:repo/history`
- `GET /api/institutions`
- `GET /api/institutions/:name`
- `GET /api/watchlist`
- `GET /api/cooccurrence/latest`
- `GET /api/sources/status`
- `GET /api/health`

示例：

```bash
curl "$PUBLIC_SITE_URL/api/latest"
curl "$PUBLIC_SITE_URL/api/topics/World%20Model/history?window=90d"
curl "$PUBLIC_SITE_URL/api/cooccurrence/latest"
```

## GitHub Actions

- `.github/workflows/ci.yml`：lint、tests、TypeScript check、Astro build、schema/env validate。
- `.github/workflows/hourly-hotspots.yml`：备用小时刷新，可手动触发。
- `.github/workflows/daily-trend-seismograph.yml`：备用日报生成，可手动触发。

Cloudflare 与 Actions 通过文件存在检查、KV lock 和 push dedupe 避免互相覆盖或重复推送。

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

## 验证

小时刷新：

```bash
python -m trend_seismograph run-hourly --hour 2026-06-13T10 --storage=file --dry-run=false
python -m trend_seismograph qa-hourly --hour 2026-06-13T10
```

每日完整报告：

```bash
python -m trend_seismograph run-daily --date 2026-06-13 --storage=file --dry-run=false
python -m trend_seismograph qa --date 2026-06-13
```

推送去重：

```bash
python -m trend_seismograph push-hotspots
python -m trend_seismograph push-hotspots
```

第二次会跳过 24 小时内相同 `dedupe_key`。

## 局限性

- arXiv affiliation 不稳定，机构识别以词典和可用 metadata 为主。
- GitHub star 增量需要先积累 snapshot，首次运行不会判定 star 暴涨。
- OpenAlex 和 Semantic Scholar 在 MVP 中是可选增强源。
- Worker 负责 Cron、锁和触发；Python 计算在 Actions、外部 pipeline 或本地运行。
- 历史不足 30 天时，基线置信度较低。

## 路线图

1. 趋势关系图谱增强。
2. AI 方向早期预警。
3. 趋势之间的因果链推断。
4. 机构竞争态势。
5. 论文-代码-数据集联动。
6. 微信公众号自动推送。
7. 个性化用户账户。
8. 用户自定义 Watchlist 页面。
9. LLM 辅助趋势解释。
10. 多站点共用趋势数据库。
11. API 订阅。
12. 企业版趋势监控。
