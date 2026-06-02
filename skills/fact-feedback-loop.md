---
name: fact-feedback-loop
description: Holographic 信任分自动校准 — 基于统计规则的 feedback 闭环。每日衰减退化 + 每周全量校准。
triggers:
  - 校准反馈
  - 反馈校准
  - fact_feedback
  - 校准记忆
  - 反馈闭环
  - fact反馈
  - 信任分
  - 记忆校准
tags:
  - memory
  - Holographic
  - feedback
  - cron
priority: 7
category: system
---

# Fact Feedback 闭环

> **核心模块**: `agent/fact_feedback_loop.py`（直接操作 SQLite，无需 tool 调用）
> **Cron**: `fact-feedback-calibrate` 每周六 11:00
> **关联 skill**: `memory-capacity-management`, `dikw-memory-flow`

## 一、系统架构

```
fact_feedback_loop.py  (源码层，直接操作 memory_store.db)
        │
        ├── analyze_health()         → 健康报告（事实库统计）
        ├── calibrate(dry_run=True)  → dry-run 校准预览
        └── calibrate(dry_run=False) → 实际校准（写入 DB）

三条规则（calibrate 自动执行）：
  1) 检索≥3次 + 零反馈 → trust -= 0.1  （冷落惩罚）
  2) 反馈/检索 > 30%   → trust += 0.05 （正反馈奖励）
  3) 零检索 > 14 天    → trust *= 0.95 （遗忘曲线）
  4) 边界保护          → trust ∈ [0.05, 0.95]
```

## 二、使用方式

### CLI 调用
```bash
# 查看健康报告
python3 -m agent.fact_feedback_loop --report

# dry-run 校准预览（不实际写入）
python3 -m agent.fact_feedback_loop --calibrate

# 实际校准
python3 -m agent.fact_feedback_loop --calibrate --apply
```

### 自动触发
- **每周六 11:00** → cron 自动校准并推送报告
- 用户说"校准反馈" → skill triggers 自动注入

## 三、校准规则详解

### 规则 1：高检索低反馈 → 降权
- 条件：retrieval_count >= 3 AND helpful_count = 0
- 动作：trust -= 0.1
- 含义：被频繁检索但从未被标记为有用 → 说明内容质量低或过时

### 规则 2：高反馈比例 → 升权
- 条件：helpful_count / retrieval_count > 0.3
- 动作：trust += 0.05
- 含义：被检索后常被标记有用 → 优质内容，提权

### 规则 3：零检索 → 衰减
- 条件：created_at > 14 days AND retrieval_count = 0 (且 trust > MIN_TRUST)
- 动作：trust *= 0.95（每次衰减 5%）
- 含义：超过两周从未被检索 → 价值低，持续衰减
- 经过约 60 次衰减（~2 年）可降至 <0.05 边界

## 四、当前状态（2026-06-02）

- **7,631** 条 fact，仅 **10** 条曾被检索
- **500** 条已首次衰减（trust -5%）
- **0** 条检索≥3次（反馈规则尚未触发）
- 反馈回路刚启动，需 1-2 个 cron 周期后才会积累有效统计

## 五、关联模块

- `agent/fact_feedback_loop.py` — 核心源码（14K，直接操作 SQLite）
- `references/fact-feedback-loop-architecture.md` — 架构参考（规则详表、DB 结构、指标解读）
- `cron: fact-feedback-calibrate` — 每周六全量校准
- `skill: memory-capacity-management` — MEMORY.md 容量管理
- `skill: dikw-memory-flow` — DIKW 分流基础流程
