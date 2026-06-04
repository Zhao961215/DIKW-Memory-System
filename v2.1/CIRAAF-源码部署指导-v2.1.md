# CIRAAF 源码自动化部署指导

> 生成日期：2026-06-03
> 对应 Hermes 版本：v0.14+
> 通用版本（部署时请按实际情况调整作者署名）

---

## 一、架构总览

CIRAAF（分类→整合→反思→完善→整理→定稿）分为三层自动化，共两个文件、一个 skill、一个 cron 任务：

```
  【Gear 1 — 机械引擎】              【Gear 2 — LLM反射】           【Gear 3 — 应用层】
  agent/cirAAF_mechanic.py           cron + brain-periodic-refactor  agent/cirAAF_mechanic.py
  (源码，零 LLM)                       skill (需 LLM)                 (源码，零 LLM)
  
  健康监控 → 报告                    矛盾检测                         执行降权/标记/新增
  统计衰减 → 条件判断                 五层分类                         更新信任分
  数据打包 → JSON 输出               修复建议 → JSON                 标记 refactored 时间戳
```

**整体无 LLM 依赖比例：~66%**（Gear 1 + Gear 3 完全源码，Gear 2 需 LLM 但可 cron 自动调度）

---

## 二、文件清单

| 文件 | 位置 | 职责 |
|------|------|------|
| `cirAAF_mechanic.py` | `~/.hermes/hermes-agent/agent/cirAAF_mechanic.py` | 机械引擎主程序 |
| `cirAAF_mechanic.sh` | `~/.hermes/scripts/cirAAF_mechanic.sh` | cron 包装脚本 |
| `brain-periodic-refactor` skill | `~/.hermes/skills/system/brain-periodic-refactor/SKILL.md` | Gear 2 LLM 反射 skill（含自动化架构文档） |
| `health_history.json` | `~/.hermes/data/cirAAF/health_history.json` | 各领域健康分历史（每周 cron 自动追加） |
| `refactor_package_*.json` | `~/.hermes/data/cirAAF/` | Gear 2 反射数据包（`--refactor-report` 生成） |

---

## 三、完整源码

### 3.1 机械引擎 — `agent/cirAAF_mechanic.py`

```python
"""
cirAAF_mechanic.py — CIRAAF 机械引擎（零 LLM 依赖）

三层分工：
  Gear 1 — 机械层（本文件）：健康监控 + 统计衰减 + 报告生成
  Gear 2 — LLM 反射层（cron skill）：复杂矛盾检测 + 重构建议
  Gear 3 — 应用层（本文件 --apply-refactor）：执行 Gear 2 输出的修复指令

使用方式：
  python3 -m agent.cirAAF_mechanic                            # 健康报告
  python3 -m agent.cirAAF_mechanic --decay                     # 衰减检查（dry-run）
  python3 -m agent.cirAAF_mechanic --decay --apply             # 实际衰减
  python3 -m agent.cirAAF_mechanic --domain 投资              # 单领域详细扫描
  python3 -m agent.cirAAF_mechanic --refactor-report           # 生成 Gear 2 数据包
  python3 -m agent.cirAAF_mechanic --apply-refactor <json>     # 应用 Gear 2 修复
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ══════════════════════════════════════════════════════════════
# 常量
# ══════════════════════════════════════════════════════════════

DB_PATH = Path.home() / ".hermes" / "memory_store.db"
REPORT_DIR = Path.home() / ".hermes" / "data" / "cirAAF"

# 五大领域定义（category 匹配 + 关键词 + 标记 + 优先级）
DOMAINS: dict[str, dict[str, Any]] = {
    "投资": {
        "categories": ["investment", "project"],
        "keywords": "PE 仓位 动量 止盈 探风 挖呗 潜风 乘风 换风 六风 基金 持仓 估值 数据源",
        "refactored_tag": "refactored:投资",
        "max_age_days": 30,
        "priority": "high",
    },
    "系统": {
        "categories": ["system", "tool"],
        "keywords": "hermes memory holographic skill cron config tool toolset gateway",
        "refactored_tag": "refactored:系统",
        "max_age_days": 45,
        "priority": "medium",
    },
    "用户": {
        "categories": ["user_pref"],
        "keywords": "用户 偏好 风格 沟通 决策",
        "refactored_tag": "refactored:用户",
        "max_age_days": 60,
        "priority": "low",
    },
    "开发": {
        "categories": ["project", "decision", "discovery"],
        "keywords": "项目 github 设计 插件 dikw github gitea",
        "refactored_tag": "refactored:开发",
        "max_age_days": 45,
        "priority": "medium",
    },
    "方法": {
        "categories": ["general", "reflect"],
        "keywords": "框架 方法论 原则 过程 元认知 思维 模型",
        "refactored_tag": "refactored:方法",
        "max_age_days": 60,
        "priority": "low",
    },
}

# 衰减规则（三条件判断通过后才执行）
DECAY_RULES = {
    "old_low_trust": {
        "condition": "created_at < ? AND trust_score > 0.3 AND trust_score < 0.7",
        "action": "trust_score * 0.95",
        "age_key": "old_zero",
        "label": "🔻 陈旧中低信任事实",
    },
    "very_old": {
        "condition": "created_at < ? AND trust_score > 0.3",
        "action": "trust_score * 0.98",
        "age_key": "refactored",
        "label": "📆 非常陈旧事实",
    },
    "refactored_outdated": {
        "condition": "tags LIKE '%refactored:%' AND updated_at < ? AND trust_score > 0.3",
        "action": "trust_score * 0.95",
        "age_key": "refactored",
        "label": "📦 整理标记过久",
    },
}


# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def since(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).isoformat()


def _compute_decay_thresholds(conn: sqlite3.Connection) -> dict[str, int]:
    """动态阈值：基于 DB 实际年龄"""
    cur = conn.execute("SELECT MIN(created_at), MAX(created_at) FROM facts")
    min_ts, max_ts = cur.fetchone()
    if not min_ts or not max_ts:
        return {"old_zero": 30, "refactored": 60}
    try:
        db_age_days = (datetime.fromisoformat(max_ts) - datetime.fromisoformat(min_ts)).days
    except Exception:
        db_age_days = 30
    return {
        "old_zero": max(21, int(db_age_days * 0.85)),
        "refactored": max(60, int(db_age_days * 2.5)),
    }


# ══════════════════════════════════════════════════════════════
# 领域健康扫描
# ══════════════════════════════════════════════════════════════

def scan_domain(conn: sqlite3.Connection, domain: str, cfg: dict) -> dict[str, Any]:
    """扫描单个领域的健康指标"""
    cats = cfg["categories"]
    ph = ",".join("?" for _ in cats)

    # 总事实数
    cur = conn.execute(f"SELECT COUNT(*) FROM facts WHERE category IN ({ph})", cats)
    total = cur.fetchone()[0]

    # 信任分布
    cur = conn.execute(f"""SELECT
        COUNT(*) as total, AVG(trust_score) as avg_trust,
        SUM(CASE WHEN trust_score >= 0.7 THEN 1 ELSE 0 END) as high,
        SUM(CASE WHEN trust_score < 0.7 AND trust_score >= 0.4 THEN 1 ELSE 0 END) as mid,
        SUM(CASE WHEN trust_score < 0.4 THEN 1 ELSE 0 END) as low
    FROM facts WHERE category IN ({ph})""", cats)
    stats = dict(cur.fetchone())

    # 零检索
    cur = conn.execute(f"SELECT COUNT(*) FROM facts WHERE category IN ({ph}) AND retrieval_count = 0", cats)
    zero_retrieval = cur.fetchone()[0]

    # refactored 标记
    cur = conn.execute(f"SELECT COUNT(*) FROM facts WHERE category IN ({ph}) AND tags LIKE ?",
                       cats + [f"%{cfg['refactored_tag']}%"])
    refactored_count = cur.fetchone()[0]

    # 最近整理时间
    cur = conn.execute(f"SELECT updated_at FROM facts WHERE category IN ({ph}) AND tags LIKE ? ORDER BY updated_at DESC LIMIT 1",
                       cats + [f"%{cfg['refactored_tag']}%"])
    row = cur.fetchone()
    last_refactored = row["updated_at"] if row else "never"

    # 健康分 = 信任分权重40 + 零检索比例30 + 基数30
    avg_trust = stats["avg_trust"] or 0.5
    health = int(min(avg_trust / 0.8 * 40, 40) + max(0, 30 - (zero_retrieval / max(total, 1)) * 30) + min(total / 200 * 30, 30))

    return {
        "domain": domain, "total_facts": total,
        "avg_trust": round(avg_trust, 3),
        "high_trust": stats["high"] or 0, "mid_trust": stats["mid"] or 0, "low_trust": stats["low"] or 0,
        "zero_retrieval": zero_retrieval, "zero_retrieval_pct": round(zero_retrieval / total * 100, 1) if total else 0,
        "refactored_count": refactored_count, "last_refactored": last_refactored,
        "health_score": health, "priority": cfg["priority"], "max_age_days": cfg["max_age_days"],
    }


# ══════════════════════════════════════════════════════════════
# 衰减条件判断（三条件独立于每领域）
# ══════════════════════════════════════════════════════════════

def _load_health_history() -> dict[str, list[dict]]:
    path = REPORT_DIR / "health_history.json"
    if path.exists():
        try: return json.loads(path.read_text())
        except: return {}
    return {}

def _save_health_snapshot(snapshot: dict[str, dict]) -> None:
    path = REPORT_DIR / "health_history.json"
    history = _load_health_history()
    today = datetime.now().strftime("%Y-%m-%d")
    for domain, stats in snapshot.items():
        if domain not in history: history[domain] = []
        if history[domain] and history[domain][-1]["date"] == today: continue
        history[domain].append({"date": today, "health": stats["health_score"],
            "total": stats["total_facts"], "high_trust": stats["high_trust"],
            "avg_trust": round(stats.get("avg_trust", 0.5), 3)})
        history[domain] = history[domain][-8:]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2))

def _check_domain_decay_readiness(conn: sqlite3.Connection, domain: str, cfg: dict,
                                   history: dict[str, list[dict]]) -> tuple[bool, str]:
    """
    三条件判断（全部满足才可衰减）：
    1. 该领域 ≥5 条事实 trust > 0.7（信任分层已形成）
    2. 健康分连续 2 周未改善（停滞）
    3. 目标事实年龄 > 中位年龄 × 1.5（动态阈值）
    """
    cats = cfg["categories"]
    ph = ",".join("?" for _ in cats)

    # 条件1
    cur = conn.execute(f"SELECT COUNT(*) FROM facts WHERE category IN ({ph}) AND trust_score > 0.7", cats)
    if cur.fetchone()[0] < 5:
        return False, f"高信任事实<5条，未形成信任分层"

    # 条件2
    dh = history.get(domain, [])
    if len(dh) < 3:
        return False, f"历史记录{len(dh)}次<3，无法判断停滞"
    recent = dh[-3:]
    if recent[-1]["health"] < recent[0]["health"]:
        return False, f"健康分仍在改善({recent[0]['health']}→{recent[-1]['health']})"

    # 条件3
    cur = conn.execute(f"SELECT created_at FROM facts WHERE category IN ({ph}) ORDER BY created_at ASC", cats)
    ages = [r[0] for r in cur.fetchall()]
    if not ages: return False, "领域无事实"
    mid_idx = len(ages) // 2
    median_age_days = (datetime.now() - datetime.fromisoformat(ages[mid_idx])).days
    threshold_days = max(14, int(median_age_days * 1.5))
    cur = conn.execute(f"SELECT COUNT(*) FROM facts WHERE category IN ({ph}) AND created_at < ?",
                       cats + [since(threshold_days)])
    if cur.fetchone()[0] < 5:
        return False, f"超中位年龄×1.5({threshold_days}天)的事实仅<5条"

    return True, f"三条件满足：高信任{cur.fetchone()}条 + 停滞{recent[-1]['health']}分 + 阈值{threshold_days}天"


# ══════════════════════════════════════════════════════════════
# 衰减执行（Gear 1）
# ══════════════════════════════════════════════════════════════

def apply_decay(dry_run: bool = True) -> list[dict]:
    conn = get_db()
    thresholds = _compute_decay_thresholds(conn)
    history = _load_health_history()

    # 每领域独立判断三条件
    domain_ready = {}
    all_stats = []
    for domain, cfg in DOMAINS.items():
        stats = scan_domain(conn, domain, cfg)
        all_stats.append(stats)
        ready, reason = _check_domain_decay_readiness(conn, domain, cfg, history)
        domain_ready[domain] = reason if not ready else "ready"

    _save_health_snapshot({s["domain"]: s for s in all_stats})

    ready_domains = [d for d, r in domain_ready.items() if r == "ready"]
    if not ready_domains:
        print("  ⏸️  当前无领域满足衰减条件：")
        for d, reason in domain_ready.items():
            print(f"    {d}: {reason}")
        conn.close()
        return [{"status": "skipped", "reason": "no_domain_ready", "details": domain_ready}]

    # 只对就绪领域执行
    ready_cats = []
    for d in ready_domains:
        ready_cats.extend(DOMAINS[d]["categories"])
    rph = ",".join("?" for _ in ready_cats)

    operations = []
    for rule_name, rule in DECAY_RULES.items():
        params = ready_cats.copy()
        if "age_key" in rule:
            params.append(since(thresholds[rule["age_key"]]))
        elif rule.get("age_days", 0) > 0:
            params.append(since(rule["age_days"]))

        cond = f"category IN ({rph}) AND {rule['condition']}"
        cur = conn.execute(f"SELECT fact_id, content, trust_score, tags FROM facts WHERE {cond}", params)
        for row in cur.fetchall():
            old = row["trust_score"]
            new = max(0.05, min(0.95, old * 0.9 if "trust_score * 0.9" in rule["action"] else old - 0.05))
            if new >= old: continue
            if not dry_run:
                conn.execute("UPDATE facts SET trust_score=?, updated_at=? WHERE fact_id=?",
                             (new, datetime.now().isoformat(), row["fact_id"]))
            operations.append({"rule": rule["label"], "fact_id": row["fact_id"],
                               "content_preview": row["content"][:60],
                               "trust": round(old, 3), "new_trust": round(new, 3)})

    if not dry_run: conn.commit()
    conn.close()
    return operations


# ══════════════════════════════════════════════════════════════
# 反射数据包（Gear 2 输入）
# ══════════════════════════════════════════════════════════════

def build_refactor_package(domain: str | None = None) -> dict:
    conn = get_db()
    package = {"generated_at": datetime.now().isoformat(), "domains": {}}
    targets = [domain] if domain else list(DOMAINS.keys())
    for d in targets:
        if d not in DOMAINS: continue
        cfg = DOMAINS[d]
        cats = cfg["categories"]
        ph = ",".join("?" for _ in cats)
        cur = conn.execute(f"""SELECT fact_id, content, category, tags, trust_score,
            retrieval_count, helpful_count, created_at, updated_at
            FROM facts WHERE category IN ({ph}) ORDER BY trust_score ASC LIMIT 200""", cats)
        facts = [dict(r) for r in cur.fetchall()]
        cur = conn.execute(f"SELECT COUNT(*) FROM facts WHERE category IN ({ph}) AND trust_score < 0.5", cats)
        low_trust_count = cur.fetchone()[0]
        cur = conn.execute(f"SELECT COUNT(*) FROM facts WHERE category IN ({ph}) AND retrieval_count=0 AND created_at<?", cats + [since(30)])
        stale_count = cur.fetchone()[0]
        package["domains"][d] = {
            "stats": {"total": len(facts), "low_trust_count": low_trust_count, "stale_count": stale_count,
                      "avg_trust": round(sum(f["trust_score"] for f in facts) / len(facts), 3) if facts else 0},
            "low_trust_facts": [{"fact_id": f["fact_id"], "content": f["content"], "trust": f["trust_score"]}
                                for f in facts if f["trust_score"] < 0.5][:30],
            "stale_facts": [{"fact_id": f["fact_id"], "content": f["content"][:80]}
                            for f in facts if f["retrieval_count"] == 0 and
                            (datetime.now() - datetime.fromisoformat(f["created_at"])).days > 30][:20],
        }
    conn.close()
    return package


# ══════════════════════════════════════════════════════════════
# 修复指令应用（Gear 3）
# ══════════════════════════════════════════════════════════════

def apply_refactor_instructions(instructions: str | list) -> list[dict]:
    """应用 Gear 2 输出的 JSON 修复指令"""
    if isinstance(instructions, str):
        path = Path(instructions)
        if path.exists():
            instructions = json.loads(path.read_text())
        else:
            instructions = json.loads(instructions)

    conn = get_db()
    results = []
    for instr in (instructions if isinstance(instructions, list) else []):
        action, fid = instr.get("action"), instr.get("fact_id")
        try:
            if action == "unhelpful" and fid:
                cur = conn.execute("SELECT trust_score FROM facts WHERE fact_id=?", (fid,))
                if row := cur.fetchone():
                    new = max(0.05, row["trust_score"] - 0.1)
                    conn.execute("UPDATE facts SET trust_score=?, updated_at=? WHERE fact_id=?",
                                 (new, datetime.now().isoformat(), fid))
                    results.append({"fact_id": fid, "action": "unhelpful", "old": row["trust_score"], "new": new})
            elif action == "update_tags" and fid:
                conn.execute("UPDATE facts SET tags=?, updated_at=? WHERE fact_id=?",
                             (instr.get("tags", ""), datetime.now().isoformat(), fid))
                results.append({"fact_id": fid, "action": "tags_updated"})
            elif action == "add":
                conn.execute("INSERT INTO facts (content, category, tags, trust_score) VALUES (?, ?, ?, 0.7)",
                             (instr.get("content", ""), instr.get("category", "general"), instr.get("tags", "")))
                results.append({"action": "added", "preview": instr.get("content", "")[:60]})
        except Exception as e:
            results.append({"action": "error", "fact_id": fid, "error": str(e)})
    conn.commit()
    conn.close()
    return results


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def print_report(all_stats):
    print("\n" + "=" * 65 + "\n  🧠 CIRAAF 大脑健康报告\n" + "=" * 65)
    for s in sorted(all_stats, key=lambda s: s["health_score"]):
        emoji = "🟢" if s["health_score"] >= 70 else "🟡" if s["health_score"] >= 40 else "🔴"
        last = s["last_refactored"][:10] if s["last_refactored"] != "never" else "从未"
        print(f"\n  {emoji} {s['domain']} (健康分: {s['health_score']}/100)")
        print(f"    事实: {s['total_facts']}条 | 均信任: {s['avg_trust']:.2f} | 零检索: {s['zero_retrieval']}条({s['zero_retrieval_pct']}%)")
        print(f"    信任分布: 🟢{s['high_trust']} 🟡{s['mid_trust']} 🔴{s['low_trust']}")
        print(f"    上次整理: {last} | 已标记: {s['refactored_count']}条")
    print("\n" + "=" * 65)


def main():
    parser = argparse.ArgumentParser(description="CIRAAF 大脑机械引擎")
    parser.add_argument("--decay", action="store_true", help="执行衰减检查（dry-run default）")
    parser.add_argument("--apply", action="store_true", help="配合 --decay 实际执行")
    parser.add_argument("--domain", type=str, help="单领域详细扫描")
    parser.add_argument("--refactor-report", action="store_true", help="生成 Gear 2 数据包")
    parser.add_argument("--apply-refactor", type=str, help="应用 Gear 2 修复指令（JSON）")
    parser.add_argument("--output", type=str, help="输出到文件")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if args.apply_refactor:
        results = apply_refactor_instructions(args.apply_refactor)
        print(f"✅ 执行 {len(results)} 条: {[r.get('action','?') for r in results[:10]]}")
        if args.output: Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if args.decay:
        ops = apply_decay(dry_run=not args.apply)
        print(f"\n{'='*50}\n  ⚙️  衰减检查 ({'dry-run' if not args.apply else '执行'})\n{'='*50}")
        if ops and isinstance(ops[0], dict) and ops[0].get("status") == "skipped":
            print(f"  ⏸️  跳过: {ops[0].get('reason', '?')}")
        else:
            print(f"  共 {len(ops)} 条匹配")
            for rn in set(op.get("rule", "?") for op in ops):
                print(f"    {rn}: {sum(1 for op in ops if op.get('rule')==rn)}条")
        if args.output: Path(args.output).write_text(json.dumps(ops, ensure_ascii=False, indent=2))
        return

    conn = get_db()
    all_stats = []
    for domain, cfg in DOMAINS.items():
        if args.domain and domain != args.domain: continue
        all_stats.append(scan_domain(conn, domain, cfg))

    if args.domain:
        s = all_stats[0]
        print(f"\n{'='*50}\n  🔍 {s['domain']}\n{'='*50}")
        for k, v in s.items(): print(f"  {k}: {v}")
        pkg = build_refactor_package(args.domain)
        if args.output: Path(args.output).write_text(json.dumps(pkg, ensure_ascii=False, indent=2))
        conn.close()
        return

    if args.refactor_report:
        pkg = build_refactor_package()
        out = args.output or str(REPORT_DIR / f"refactor_package_{datetime.now().strftime('%Y%m%d')}.json")
        Path(out).write_text(json.dumps(pkg, ensure_ascii=False, indent=2))
        print(f"✅ 数据包: {out}")
        for d, i in pkg["domains"].items():
            print(f"  {d}: {i['stats']['total']}条, 低信任{i['stats']['low_trust_count']}条, 陈旧{i['stats']['stale_count']}条")
        conn.close()
        return

    print_report(all_stats)
    conn.close()


if __name__ == "__main__":
    main()
```

### 3.2 Cron 包装脚本 — `~/.hermes/scripts/cirAAF_mechanic.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
AGENT_DIR="$HERMES_HOME/hermes-agent"
SCRIPT="$AGENT_DIR/agent/cirAAF_mechanic.py"

cd "$AGENT_DIR"
[ -d "$AGENT_DIR/venv" ] && source "$AGENT_DIR/venv/bin/activate"
[ -d "$AGENT_DIR/.venv" ] && source "$AGENT_DIR/.venv/bin/activate"

echo "  🧠 CIRAAF 周健康报告 | $(date +%Y-%m-%d\ %H:%M)"
python3 -m agent.cirAAF_mechanic

echo ""
echo "  ⚙️  机械衰减检查"
python3 -m agent.cirAAF_mechanic --decay
```

### 3.3 Gear 2 反射 Skill — `brain-periodic-refactor`

已在 skill 中集成完整自动化架构文档（三齿轮、每个齿轮的命令、cron 绑定、领域定义表），此处不重复贴全文。路径：`~/.hermes/skills/system/brain-periodic-refactor/SKILL.md`。

---

## 四、部署步骤

### 4.1 首次部署

> ⚠️ **关键修复（2026-06-04）**：旧版部署命令有几处会让 cron 任务**静默失败**——
> 1. `cp cirAAF_mechanic.py` 用裸名（仓库根没这个文件，正确路径是 `agent/cirAAF_mechanic.py`）
> 2. `cp cirAAF_mechanic.sh` 同样问题（应在 `scripts/` 子目录）
> 3. cron 任务 `script="cirAAF_mechanic.sh"` 是裸名 + 没设 `workdir` → 调度时找不到脚本（jobs.py 源码注释明示"cron jobs run detached from any shell cwd, so relative paths have no stable meaning"）
>
> **修复后命令**（下面所有 `cp` 都从仓库根目录执行，确保源路径是仓库相对路径）：

```bash
# 1. CIRAAF 机械引擎（Gear 1 零 LLM）
cp agent/cirAAF_mechanic.py ~/.hermes/hermes-agent/agent/

# 2. Cron 包装脚本（72 行新版，含 --decay 段）
cp scripts/cirAAF_mechanic.sh ~/.hermes/scripts/cirAAF_mechanic.sh
chmod +x ~/.hermes/scripts/cirAAF_mechanic.sh

# 3. Gear 2 LLM 反射 skill（brain-periodic-refactor）
mkdir -p ~/.hermes/skills/system
cp -r skills/system/brain-periodic-refactor ~/.hermes/skills/system/
```

```bash
# 4. 创建 cron 任务（必须 workdir + script 绝对路径）
hermes cron add --name "CIRAAF 周健康报告" \
    --schedule "0 10 * * 0" \
    --no-agent \
    --workdir "/home/$USER/.hermes/hermes-agent" \
    --script "/home/$USER/.hermes/scripts/cirAAF_mechanic.sh" \
    --deliver origin

# 5. 部署 information_flow_health.py（信息流 v2 健康检查）
cp scripts/information_flow_health.py ~/.hermes/scripts/

# 6. 健康验证（默认输出健康报告；--decay 三条件检查；--domain 详细扫描）
python3 -m agent.cirAAF_mechanic
python3 -m agent.cirAAF_mechanic --decay
python3 -m agent.cirAAF_mechanic --domain 投资
python3 ~/.hermes/scripts/information_flow_health.py
```

### 4.2 验证部署

```bash
# 健康报告正常
python3 -m agent.cirAAF_mechanic

# 衰减检查正常（三条件未满足则跳过）
python3 -m agent.cirAAF_mechanic --decay

# 单领域扫描正常
python3 -m agent.cirAAF_mechanic --domain 投资

# cron 已配置
cronjob action=list | grep CIRAAF
```

---

## 五、与已有系统的集成

### 5.1 三层保养流水线

```
P1.3 单条校准（SOUL铁律，日常对话中 → 模型手动）
    │ 发现错误事实 → 当场 fact_feedback
    ▼
fact_feedback_loop.py（微观，每周六 11:00 → 源码自动）
    │ 统计规则：降权零检索/升权高helpful → 绕过模型
    ▼
CIRAAF（宏观，每周健康监控 + 每月重构 → Gear1/3源码 + Gear2 cron）
    │ 检查领域级结构一致性
    ▼
      三层从微观到宏观形成完整保养闭环
```

### 5.2 Gear 2 与已有 skill 的配合

Gear 2（LLM cron）执行时需加载 `brain-periodic-refactor` skill 和 `--refactor-report` 生成的数据包：

```bash
# 创建 Gear 2 cron（待 DB 成熟后可配置）
cronjob action=create \
  name="CIRAAF Gear2 月反射" \
  schedule="0 10 1 * *" \      # 每月1日
  skills="brain-periodic-refactor" \
  prompt="读取 ~/.hermes/data/cirAAF/refactor_package_*.json，执行 R+A 步骤，
          输出修复指令到 ~/.hermes/data/cirAAF/fix_instructions_$(date +%Y%m%d).json"
```

### 5.3 Gear 3 集成

```bash
# Gear 2 完成后自动执行
python3 -m agent.cirAAF_mechanic --apply-refactor ~/.hermes/data/cirAAF/fix_instructions_YYYYMMDD.json
```

---

## 六、衰减条件判断逻辑（核心设计）

```python
# 每领域独立判断，不是全局一棍子
for domain in ["投资", "系统", "用户", "开发", "方法"]:
    # 条件1：信任分层已形成
    if count(trust > 0.7) < 5:
        skip("高信任事实不足")
    
    # 条件2：停滞（健康分连续2周未上升）
    if len(health_history) < 3:
        skip("历史数据不足")
    if recent[0].health < recent[-1].health:
        skip("健康分在改善中")
    
    # 条件3：动态年龄阈值
    median_age = facts[count//2].age
    threshold = max(14, median_age * 1.5)
    if count(age > threshold) < 5:
        skip("目标事实不足")
    
    # 三条件均满足 → 执行衰减
    execute_decay(domain)
```

**为什么不用硬编码天数？** 因为：
- 数据库早期（<30天）所有事实几乎同龄，按天数衰减打一片
- 不同领域成熟度不同（投资 332 条高信任 vs 方法 63 条）
- 动态中位年龄 × 1.5 适配事实分布的真实形状

---

## 七、状态文件格式

### health_history.json

```json
{
  "投资": [
    {"date": "2026-06-03", "health": 63, "total": 1133, "high_trust": 332, "avg_trust": 0.679},
    {"date": "2026-06-10", "health": 64, "total": 1140, "high_trust": 335, "avg_trust": 0.682},
    ...
  ]
}
```

### refactor_package_YYYYMMDD.json

```json
{
  "generated_at": "2026-06-03T02:30:00",
  "domains": {
    "方法": {
      "stats": {"total": 639, "low_trust_count": 68, "stale_count": 0, "avg_trust": 0.55},
      "low_trust_facts": [
        {"fact_id": 272, "content": "雪球 cron 任务中的持有记录...", "trust": 0.48}
      ],
      "stale_facts": []
    }
  }
}
```

### Gear 2 修复指令 JSON 格式

```json
[
  {"action": "unhelpful", "fact_id": 123},
  {"action": "add", "content": "核心方法论", "tags": "refactored:投资,体系", "category": "investment"},
  {"action": "update_tags", "fact_id": 456, "tags": "refactored:投资"},
  {"action": "update_trust", "fact_id": 789, "trust": 0.8}
]
```

---

## 八、常见问题

### Q: 为什么 `--decay` 总是跳过？
A: 三条件自动判断。用 `--decay` 查看每个领域的具体跳过原因。最常见：健康历史不足3次（等下周 cron）或信任分层未形成（需要模型手动静默升权）。

### Q: Gear 2 什么时候配置？
A: 当 `--refactor-report` 显示某领域健康分 < 60 且 DB > 60 天时。目前（DB 24 天）过早。

### Q: 如果 session 归档改了，需要额外操作吗？
A: 不需要。`session_archive.py` 改 7 天归档后，SQLite session_search 仍保留 7 天自动清理，两者独立。

### Q: 怎样添加新领域？
A: 在 `DOMAINS` 字典新增条目，配置 `categories`（对应事实的 category 字段）和搜索关键词即可，无需改其他代码。
