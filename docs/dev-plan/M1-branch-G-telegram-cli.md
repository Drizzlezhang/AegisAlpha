# Branch G — Telegram + CLI + Lightweight + Pipeline Runner + 集成 — Plan Prompt

> **分支**: `feat/m1-integration`
> **估时**: 3 天
> **依赖**: A-F 全部完成
> **子 Agent**: `m1-integration`
> **前置阅读**: `AGENTS.md` 第 13/16 节 + `docs/aegis-2.0-tech-arch.md` Section 9

---

## 目标

将 A-F 所有组件串联:Full Pipeline Runner + Lightweight Pipeline 雏形 + Telegram 推送 + APScheduler + CLI 入口 + 端到端集成测试。

## 范围

### Pipeline Runner

- `pipeline/graph_full.py`:手动装配 StateGraph(M1 不用 graph_builder)
  - START → DataHarvester → [Trend/Phase, Level, Options S1](并行) → Debate → Options S2 → Research Manager → Portfolio Orchestrator → Risk Gate → END
- `pipeline/graph_lightweight.py`:最小巡检子图
  - START → DataHarvester(lightweight mode) → Trend/Phase(轻) → Level(轻) → 简单 health check → END
  - **v1.2**: 输出 `state.passive_health_alerts` + 更新 `state.health_scores`
  - 全部 Agent `llm_dependency=False` 校验(单测 spy 确保无 LLMClient 调用)
- `pipeline/runner.py`:
  - `run_full(ticker, mode)` — 调 graph_full
  - `run_lightweight(tickers_passive)` — 调 graph_lightweight
  - 记录 `agent_timings` + 总耗时

### Telegram Notifier

- `notifier/telegram.py`:
  - 格式化推荐消息(📊 新建仓 / ⚙️ 持仓操作 / ⚠️ 被拦截)
  - **v1.2 新增**: 🔍 Lightweight 巡检消息 + ⏰ Trigger 占位前缀
  - 4000 字符自动拆分
  - 错误告警(❗)
  - 全局 `🧪 [Beta]` 前缀
- 消息模板: `config/prompts/telegram_recommendation.j2` / `telegram_lightweight.j2` / `telegram_error.j2`

### APScheduler

- `schedule.yaml`:
  ```yaml
  jobs:
    full_pre_market:
      trigger: cron
      hour: 8
      minute: 0
      timezone: US/Eastern
      func: aegis.pipeline.runner:run_full
      kwargs: {mode: "pre-market"}
    full_post_market:
      trigger: cron
      hour: 17
      minute: 0
      timezone: US/Eastern
      func: aegis.pipeline.runner:run_full
      kwargs: {mode: "post-market"}
    lightweight_check:
      trigger: cron
      hour: "8,17"
      minute: 5
      timezone: US/Eastern
      func: aegis.pipeline.runner:run_lightweight
  ```

### Typer CLI

- `aegis run --ticker QQQ --mode pre-market` → Full Pipeline
- `aegis run --ticker QQQ --mode lightweight` → Lightweight Pipeline
- `aegis run --ticker QQQ --mode post-market` → Full Pipeline
- `aegis schedule start` → APScheduler 常驻
- `aegis health` → 各 Tool 连通性 + DB 检查

### 集成测试

- `tests/integration/test_full_pipeline.py`:端到端 mock 所有外部,验证 state 流转完整
- `tests/integration/test_lightweight_pipeline.py`:验证无 LLM 调用 + health_alerts 输出
- `tests/e2e/test_telegram_output.py`:mock Telegram API,验证消息格式

## 文件清单

```
backend/aegis/
├── pipeline/
│   ├── graph_full.py              # StateGraph 手动装配
│   ├── graph_lightweight.py       # Lightweight 子图
│   └── runner.py                  # run_full / run_lightweight
├── notifier/
│   └── telegram.py                # TelegramNotifier
└── cli.py                         # 完整 CLI(run / schedule / health)

backend/config/
├── schedule.yaml
└── prompts/
    ├── telegram_recommendation.j2
    ├── telegram_lightweight.j2
    └── telegram_error.j2

backend/tests/
├── integration/
│   ├── test_full_pipeline.py
│   └── test_lightweight_pipeline.py
└── e2e/
    └── test_telegram_output.py
```

## 验收

- [ ] `aegis run --ticker QQQ --mode pre-market` → Telegram 收到完整推荐
- [ ] `aegis run --ticker QQQ --mode lightweight` → Telegram 收到 🔍 巡检消息
- [ ] Lightweight Pipeline 确认无 LLM 调用(spy 验证)
- [ ] Full Pipeline 总时长 ≤ 5 分钟
- [ ] `passive_health_alerts` 正确生成
- [ ] 消息含正确前缀(🧪 [Beta] + 📊/⚙️/⚠️/🔍)
- [ ] 4000 字符拆分正确
- [ ] `schedule.yaml` 三套 cron job 可解析
- [ ] 集成测试全绿
- [ ] **M1 全量验收标准 11 条全部满足**

### 不允许

- 不实现 graph_builder 自动装配(M4)
- 不实现 trigger_runner 小时巡检(M2)
- 不实现前端(M2)
- 不修改 A-F 分支代码(如发现 bug,提 fix PR 到对应分支)
