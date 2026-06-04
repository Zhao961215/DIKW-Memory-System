"""
cirAAF_mechanic.py — CIRAAF 机械引擎（零 LLM 依赖）

三层分工：
  Gear 1 — 机械层（本文件）：健康监控 + 统计降权 + 报告生成
  Gear 2 — LLM 反射层（cron skill）：复杂矛盾检测 + 重构建议
  Gear 3 — 应用层（本文件 --apply-refactor）：执行 Gear 2 输出的修复指令

使用方式：
  python3 -m agent.cirAAF_mechanic                            # 健康报告
  python3 -m agent.cirAAF_mechanic --decay                     # 执行机械衰减（dry-run）
  python3 -m agent.cirAAF_mechanic --decay --apply             # 实际衰减
  python3 -m agent.cirAAF_mechanic --domain 投资              # 单领域详细扫描
  python3 -m agent.cirAAF_mechanic --refactor-report           # 生成给 LLM cron 用的反射数据包
  python3 -m agent.cirAAF_mechanic --apply-refactor <json>     # 应用 Gear 2 的修复指令
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ── Constants ──────────────────────────────────────────────────────────────

DB_PATH = Path.home() / ".hermes" / "memory_store.db"
REPORT_DIR = Path.home() / ".hermes" / "data" / "cirAAF"

# 五大领域定义（关键词用于 category 模糊匹配 + 内容关键词检索）
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
        "keywords": "用户 偏好 风格 主上 沟通 决策",
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

def _compute_decay_thresholds(conn: sqlite3.Connection) -> dict[str, int]:
    """动态计算衰减阈值：基于数据库实际年龄"""
    cur = conn.execute("SELECT MIN(created_at), MAX(created_at) FROM facts")
    min_ts, max_ts = cur.fetchone()
    if not min_ts or not max_ts:
        return {"old_zero": 30, "refactored": 60}
    try:
        db_age_days = (datetime.fromisoformat(max_ts) - datetime.fromisoformat(min_ts)).days
    except Exception:
        db_age_days = 30
    return {
        "old_zero": max(21, int(db_age_days * 0.85)),  # 85% of DB age, min 21 days
        "refactored": max(60, int(db_age_days * 2.5)),  # 250% of DB age, min 60 days
    }


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
        "age_key": "refactored",  # 更宽松的时间阈值
        "label": "📆 超过DB年龄150%的旧事实",
    },
    "refactored_outdated": {
        "condition": "tags LIKE '%refactored:%' AND updated_at < ? AND trust_score > 0.3",
        "action": "trust_score * 0.95",
        "age_key": "refactored",
        "label": "📦 整理标记过久",
    },
}

# ── Helpers ────────────────────────────────────────────────────────────────


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def since(days: int) -> str:
    """返回 days 天前的 ISO 时间戳"""
    return (datetime.now() - timedelta(days=days)).isoformat()


# ── Domain Metrics ─────────────────────────────────────────────────────────


def scan_domain(conn: sqlite3.Connection, domain: str, cfg: dict) -> dict[str, Any]:
    """扫描单个领域的健康指标"""
    cats = cfg["categories"]
    placeholders = ",".join("?" for _ in cats)
    safe_age = since(14)

    # 该领域总事实数
    cur = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE category IN ({placeholders})",
        cats,
    )
    total = cur.fetchone()[0]

    # 各信任分区间分布
    cur = conn.execute(
        f"""SELECT
            COUNT(*) as total,
            AVG(trust_score) as avg_trust,
            SUM(CASE WHEN trust_score >= 0.7 THEN 1 ELSE 0 END) as high,
            SUM(CASE WHEN trust_score < 0.7 AND trust_score >= 0.4 THEN 1 ELSE 0 END) as mid,
            SUM(CASE WHEN trust_score < 0.4 THEN 1 ELSE 0 END) as low
        FROM facts WHERE category IN ({placeholders})""",
        cats,
    )
    stats = dict(cur.fetchone())

    # 零检索事实
    cur = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE category IN ({placeholders}) AND retrieval_count = 0",
        cats,
    )
    zero_retrieval = cur.fetchone()[0]

    # 已标记 refactored 的事实
    cur = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE category IN ({placeholders}) AND tags LIKE ?",
        cats + [f"%{cfg['refactored_tag']}%"],
    )
    refactored_count = cur.fetchone()[0]

    # 最近 refactored 时间
    cur = conn.execute(
        f"""SELECT updated_at FROM facts
            WHERE category IN ({placeholders}) AND tags LIKE ?
            ORDER BY updated_at DESC LIMIT 1""",
        cats + [f"%{cfg['refactored_tag']}%"],
    )
    row = cur.fetchone()
    last_refactored = row["updated_at"] if row else "never"

    # 健康分 (0-100)
    health = _compute_health(total, stats["avg_trust"] or 0.5, zero_retrieval, total)

    return {
        "domain": domain,
        "total_facts": total,
        "avg_trust": round(stats["avg_trust"] or 0, 3),
        "high_trust": stats["high"] or 0,
        "mid_trust": stats["mid"] or 0,
        "low_trust": stats["low"] or 0,
        "zero_retrieval": zero_retrieval,
        "zero_retrieval_pct": round(zero_retrieval / total * 100, 1) if total else 0,
        "refactored_count": refactored_count,
        "last_refactored": last_refactored,
        "health_score": health,
        "priority": cfg["priority"],
        "max_age_days": cfg["max_age_days"],
    }


def _compute_health(
    total: int, avg_trust: float, zero_ret: int, denom: int
) -> int:
    """健康分 = 信任分权重40 + 零检索比例权重30 + 基数权重30"""
    trust_score = min(avg_trust / 0.8 * 40, 40) if avg_trust else 20
    zero_score = max(0, 30 - (zero_ret / max(denom, 1)) * 30)
    count_score = min(total / 200 * 30, 30) if total > 0 else 0
    return int(trust_score + zero_score + count_score)


# ── Decay Engine (Gear 1) ──────────────────────────────────────────────────


def _load_health_history() -> dict[str, list[dict]]:
    """加载历史健康分记录（用于判断是否连续停滞）"""
    path = REPORT_DIR / "health_history.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_health_snapshot(snapshot: dict[str, dict]) -> None:
    """记录本轮健康快照"""
    path = REPORT_DIR / "health_history.json"
    history = _load_health_history()

    today = datetime.now().strftime("%Y-%m-%d")
    for domain, stats in snapshot.items():
        if domain not in history:
            history[domain] = []
        # 同一天不重复记录
        if history[domain] and history[domain][-1]["date"] == today:
            continue
        history[domain].append({
            "date": today,
            "health": stats["health_score"],
            "total": stats["total_facts"],
            "high_trust": stats["high_trust"],
            "avg_trust": round(stats.get("avg_trust", 0.5), 3),
        })
        # 只保留最近8周记录
        history[domain] = history[domain][-8:]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2))


def _check_domain_decay_readiness(
    conn: sqlite3.Connection,
    domain: str,
    cfg: dict,
    history: dict[str, list[dict]],
) -> tuple[bool, str]:
    """
    判断一个领域是否达到衰减条件。
    返回 (ready, reason)。
    """
    cats = cfg["categories"]
    ph = ",".join("?" for _ in cats)

    # 条件1：至少有5条事实 trust > 0.7（表明模型手动升权形成了分层）
    cur = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE category IN ({ph}) AND trust_score > 0.7",
        cats,
    )
    high_trust_count = cur.fetchone()[0]
    if high_trust_count < 5:
        return False, f"高信任事实仅{high_trust_count}条(<5)，未形成信任分层"

    # 条件2：该领域健康分连续2周未改善（停滞判断）
    domain_hist = history.get(domain, [])
    if len(domain_hist) >= 3:
        # 看最近3次记录：如果最近2周的健康分没有上升趋势
        recent = domain_hist[-3:]
        if recent[-1]["health"] >= recent[0]["health"]:
            # 没上升 → 停滞
            pass  # 停滞了，符合条件2
        else:
            # 正在改善中，暂时不衰减
            return False, f"健康分仍在改善({recent[0]['health']}→{recent[-1]['health']})，等待稳定"
    else:
        # 数据不够，暂不判断停滞
        return False, f"历史记录不足{len(domain_hist)}次(<3)，无法判断停滞趋势"

    # 条件3：事实年龄 > 中位年龄 * 1.5（动态阈值）
    cur = conn.execute(
        f"SELECT created_at FROM facts WHERE category IN ({ph}) ORDER BY created_at ASC",
        cats,
    )
    ages = [r[0] for r in cur.fetchall()]
    if not ages:
        return False, "领域无事实"

    mid_idx = len(ages) // 2
    median_age_str = ages[mid_idx]
    median_age_days = (datetime.now() - datetime.fromisoformat(median_age_str)).days
    threshold_days = max(14, int(median_age_days * 1.5))

    cur = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE category IN ({ph}) AND created_at < ?",
        cats + [since(threshold_days)],
    )
    old_count = cur.fetchone()[0]
    if old_count < 5:
        return False, f"超过中位年龄1.5倍({threshold_days}天)的事实仅{old_count}条，目标太少"

    return True, f"三条件均满足：高信任{high_trust_count}条 + 停滞{recent[-1]['health']}分不变 + 年龄阈值{threshold_days}天"


def apply_decay(dry_run: bool = True) -> list[dict]:
    """应用机械衰减规则，返回操作记录"""
    conn = get_db()
    thresholds = _compute_decay_thresholds(conn)
    history = _load_health_history()

    # 替换旧版年龄守卫：改为每领域独立判断三条件
    # 先扫描所有领域健康状态（复用 scan_domain）
    domain_ready: dict[str, str] = {}
    all_stats = []
    for domain, cfg in DOMAINS.items():
        stats = scan_domain(conn, domain, cfg)
        all_stats.append(stats)
        ready, reason = _check_domain_decay_readiness(conn, domain, cfg, history)
        domain_ready[domain] = reason if not ready else "ready"

    # 保存本轮快照供下周判断用
    snapshot = {s["domain"]: s for s in all_stats}
    _save_health_snapshot(snapshot)

    # 统计哪些领域满足条件
    ready_domains = [d for d, r in domain_ready.items() if r == "ready"]
    if not ready_domains:
        print(f"  ⏸️  当前无领域满足衰减条件：")
        for d, reason in domain_ready.items():
            print(f"    {d}: {reason}")
        conn.close()
        return [{"status": "skipped", "reason": "no_domain_ready", "details": domain_ready}]

    operations: list[dict] = []

    # 只对满足条件的领域执行衰减
    ready_categories: list[str] = []
    for domain in ready_domains:
        ready_categories.extend(DOMAINS[domain]["categories"])
    ready_ph = ",".join("?" for _ in ready_categories)

    for rule_name, rule in DECAY_RULES.items():
        params = ready_categories.copy()
        if "age_key" in rule:
            params.append(since(thresholds[rule["age_key"]]))
        elif rule.get("age_days", 0) > 0:
            params.append(since(rule["age_days"]))

        # 加 category 过滤：只衰减就绪领域内的事实
        condition_with_domain = f"category IN ({ready_ph}) AND {rule['condition']}"
        cur = conn.execute(
            f"SELECT fact_id, content, trust_score, tags FROM facts WHERE {condition_with_domain}",
            params,
        )
        candidates = cur.fetchall()

        for row in candidates:
            old_trust = row["trust_score"]
            # 计算新信任分
            new_trust = max(0.05, min(0.95, old_trust * 0.9 if "trust_score * 0.9" in rule["action"] else old_trust - 0.05))
            if new_trust >= old_trust:
                continue  # 已到边界

            if not dry_run:
                conn.execute(
                    "UPDATE facts SET trust_score = ?, updated_at = ? WHERE fact_id = ?",
                    (new_trust, datetime.now().isoformat(), row["fact_id"]),
                )

            operations.append({
                "rule": rule["label"],
                "fact_id": row["fact_id"],
                "content_preview": row["content"][:60],
                "trust": round(old_trust, 3),
                "new_trust": round(new_trust, 3),
                "tags": row["tags"],
            })

    if not dry_run:
        conn.commit()
    conn.close()
    return operations


# ── Refactor Report (for Gear 2 LLM cron) ──────────────────────────────────


def build_refactor_package(domain: str | None = None) -> dict:
    """生成供 LLM cron 使用的反射数据包"""
    conn = get_db()

    package = {
        "generated_at": datetime.now().isoformat(),
        "mode": "full" if not domain else f"single:{domain}",
        "domains": {},
    }

    targets = [domain] if domain else list(DOMAINS.keys())
    for d in targets:
        if d not in DOMAINS:
            continue
        cfg = DOMAINS[d]
        cats = cfg["categories"]
        placeholders = ",".join("?" for _ in cats)

        # 收集所有该领域事实
        cur = conn.execute(
            f"""SELECT fact_id, content, category, tags, trust_score,
                       retrieval_count, helpful_count, created_at, updated_at
                FROM facts WHERE category IN ({placeholders})
                ORDER BY trust_score ASC LIMIT 200""",
            cats,
        )
        facts = [dict(r) for r in cur.fetchall()]

        # 统计指标
        cur = conn.execute(
            f"SELECT COUNT(*) FROM facts WHERE category IN ({placeholders}) AND trust_score < 0.5",
            cats,
        )
        low_trust_count = cur.fetchone()[0]

        cur = conn.execute(
            f"SELECT COUNT(*) FROM facts WHERE category IN ({placeholders}) AND retrieval_count = 0 AND created_at < ?",
            cats + [since(30)],
        )
        stale_count = cur.fetchone()[0]

        package["domains"][d] = {
            "config": {k: v for k, v in cfg.items() if k != "categories"},
            "stats": {
                "total": len(facts),
                "low_trust_count": low_trust_count,
                "stale_count": stale_count,
                "avg_trust": round(sum(f["trust_score"] for f in facts) / len(facts), 3) if facts else 0,
            },
            "low_trust_facts": [
                {"fact_id": f["fact_id"], "content": f["content"], "trust": f["trust_score"]}
                for f in facts if f["trust_score"] < 0.5
            ][:30],
            "stale_facts": [
                {"fact_id": f["fact_id"], "content": f["content"][:80]}
                for f in facts if f["retrieval_count"] == 0 and (datetime.now() - datetime.fromisoformat(f["created_at"])).days > 30
            ][:20],
        }

    conn.close()
    return package


# ── Apply Refactor (Gear 3) ────────────────────────────────────────────────


def apply_refactor_instructions(instructions_file: str) -> list[dict]:
    """
    应用 Gear 2（LLM cron）输出的修复指令 JSON。

    指令格式：
    [
        {"action": "unhelpful", "fact_id": 123},
        {"action": "add", "content": "...", "tags": "...", "category": "..."},
        {"action": "update_tags", "fact_id": 456, "tags": "refactored:投资,体系"},
        {"action": "update_trust", "fact_id": 789, "trust": 0.8},
    ]
    """
    path = Path(instructions_file)
    if not path.exists():
        print(f"❌ 文件不存在: {instructions_file}")
        return []

    with open(path) as f:
        instructions = json.load(f)

    # 如果入参是 JSON 字符串而非文件路径
    if isinstance(instructions_file, str) and instructions_file.startswith("["):
        instructions = json.loads(instructions_file)

    conn = get_db()
    results = []

    for instr in instructions:
        action = instr.get("action")
        fid = instr.get("fact_id")
        try:
            if action == "unhelpful" and fid:
                cur = conn.execute("SELECT trust_score FROM facts WHERE fact_id = ?", (fid,))
                row = cur.fetchone()
                if row:
                    new_trust = max(0.05, row["trust_score"] - 0.1)
                    conn.execute(
                        "UPDATE facts SET trust_score = ?, updated_at = ? WHERE fact_id = ?",
                        (new_trust, datetime.now().isoformat(), fid),
                    )
                    results.append({"fact_id": fid, "action": "unhelpful", "old_trust": row["trust_score"], "new_trust": new_trust})
            elif action == "helpful" and fid:
                cur = conn.execute("SELECT trust_score FROM facts WHERE fact_id = ?", (fid,))
                row = cur.fetchone()
                if row:
                    new_trust = min(0.95, row["trust_score"] + 0.05)
                    conn.execute(
                        "UPDATE facts SET trust_score = ?, updated_at = ? WHERE fact_id = ?",
                        (new_trust, datetime.now().isoformat(), fid),
                    )
                    results.append({"fact_id": fid, "action": "helpful", "old_trust": row["trust_score"], "new_trust": new_trust})
            elif action == "update_tags" and fid:
                conn.execute(
                    "UPDATE facts SET tags = ?, updated_at = ? WHERE fact_id = ?",
                    (instr.get("tags", ""), datetime.now().isoformat(), fid),
                )
                results.append({"fact_id": fid, "action": "tags_updated"})
            elif action == "update_trust" and fid:
                new_trust = max(0.05, min(0.95, instr.get("trust", 0.5)))
                conn.execute(
                    "UPDATE facts SET trust_score = ?, updated_at = ? WHERE fact_id = ?",
                    (new_trust, datetime.now().isoformat(), fid),
                )
                results.append({"fact_id": fid, "action": "trust_set", "new_trust": new_trust})
            elif action == "add":
                # 通过 SQLite 直接插入（绕过 fact_store 工具）
                content = instr.get("content", "")
                tags = instr.get("tags", "")
                cat = instr.get("category", "general")
                conn.execute(
                    "INSERT INTO facts (content, category, tags, trust_score) VALUES (?, ?, ?, 0.7)",
                    (content, cat, tags),
                )
                results.append({"action": "added", "content_preview": content[:60]})
            else:
                results.append({"action": "skipped", "reason": f"unknown action: {action}", "instr": instr})
        except Exception as e:
            results.append({"action": "error", "fact_id": fid, "error": str(e)})

    conn.commit()
    conn.close()
    return results


# ── CLI ────────────────────────────────────────────────────────────────────


def print_report(all_stats: list[dict]) -> None:
    """打印友好报告"""
    print("\n" + "=" * 65)
    print("  🧠 CIRAAF 大脑健康报告")
    print("=" * 65)

    # 按健康分排序
    sorted_stats = sorted(all_stats, key=lambda s: s["health_score"])

    for s in sorted_stats:
        emoji = "🟢" if s["health_score"] >= 70 else "🟡" if s["health_score"] >= 40 else "🔴"
        last_ref = s["last_refactored"][:10] if s["last_refactored"] != "never" else "从未"
        print(f"\n  {emoji} {s['domain']}  (健康分: {s['health_score']}/100)")
        print(f"    事实: {s['total_facts']}条 | 均信任: {s['avg_trust']:.2f} | 零检索: {s['zero_retrieval']}条({s['zero_retrieval_pct']}%)")
        print(f"    信任分布: 🟢{s['high_trust']} 🟡{s['mid_trust']} 🔴{s['low_trust']}")
        print(f"    上次整理: {last_ref} | 已标记: {s['refactored_count']}条")

    print("\n" + "=" * 65)
    print(f"  📋 建议关注:")
    for s in sorted_stats[:3]:
        if s["health_score"] < 70:
            print(f"    - {s['domain']}: 健康分{s['health_score']}，{s['zero_retrieval_pct']}%零检索")
    print()


def main():
    parser = argparse.ArgumentParser(description="CIRAAF 大脑机械引擎")
    parser.add_argument("--decay", action="store_true", help="执行机械衰减（dry-run 默认）")
    parser.add_argument("--apply", action="store_true", help="配合 --decay 实际执行")
    parser.add_argument("--domain", type=str, help="单领域详细扫描")
    parser.add_argument("--refactor-report", action="store_true", help="生成 Gear 2 反射数据包")
    parser.add_argument("--apply-refactor", type=str, help="应用 Gear 2 修复指令（JSON 文件路径）")
    parser.add_argument("--output", type=str, help="输出到文件")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Gear 3: 应用修复指令 ──
    if args.apply_refactor:
        results = apply_refactor_instructions(args.apply_refactor)
        print(f"✅ 已执行 {len(results)} 条修复指令")
        for r in results[:10]:
            print(f"  {r}")
        if args.output:
            Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2))
        return

# ── Gear 1: 机械衰减 ──
    if args.decay:
        ops = apply_decay(dry_run=not args.apply)
        action = "将" if not args.apply else "已"
        print(f"\n{'='*50}")
        print(f"  ⚙️  机械衰减 ({'dry-run' if not args.apply else '实际执行'})")
        print(f"{'='*50}")
        # 处理跳过的 case
        if ops and ops[0].get("status") == "skipped":
            print(f"  ⏸️  跳过: {ops[0].get('reason', 'unknown')}")
        else:
            print(f"  共 {len(ops)} 条匹配衰减规则")
            for rule_name in set(op.get("rule", "?") for op in ops):
                count = sum(1 for op in ops if op.get("rule") == rule_name)
                print(f"    {rule_name}: {count}条")
        if args.output:
            Path(args.output).write_text(json.dumps(ops, ensure_ascii=False, indent=2))
        return

    # ── 全领域扫描 ──
    conn = get_db()
    all_stats = []
    for domain, cfg in DOMAINS.items():
        if args.domain and domain != args.domain:
            continue
        stats = scan_domain(conn, domain, cfg)
        all_stats.append(stats)
    conn.close()

    # ── 单领域详细扫描 ──
    if args.domain:
        s = all_stats[0]
        print(f"\n{'='*50}")
        print(f"  🔍 详细扫描: {s['domain']}")
        print(f"{'='*50}")
        for k, v in s.items():
            print(f"  {k}: {v}")
        package = build_refactor_package(args.domain)
        if args.output:
            Path(args.output).write_text(json.dumps(package, ensure_ascii=False, indent=2))
        else:
            print(f"\n  低信任事实 ({len(package['domains'][args.domain]['low_trust_facts'])}条):")
            for f in package["domains"][args.domain]["low_trust_facts"][:5]:
                print(f"    #{f['fact_id']} trust={f['trust']:.2f}: {f['content'][:60]}")
            print(f"\n  陈旧事实 ({len(package['domains'][args.domain]['stale_facts'])}条):")
            for f in package["domains"][args.domain]["stale_facts"][:5]:
                print(f"    #{f['fact_id']}: {f['content'][:60]}")
        return

    # ── 生成反射数据包 ──
    if args.refactor_report:
        package = build_refactor_package()
        output_path = args.output or str(REPORT_DIR / f"refactor_package_{datetime.now().strftime('%Y%m%d')}.json")
        Path(output_path).write_text(json.dumps(package, ensure_ascii=False, indent=2))
        print(f"✅ 反射数据包已生成: {output_path}")
        print(f"   覆盖领域: {list(package['domains'].keys())}")
        for d, info in package["domains"].items():
            print(f"   {d}: {info['stats']['total']}条, 低信任{info['stats']['low_trust_count']}条, 陈旧{info['stats']['stale_count']}条")
        return

    # ── 默认：健康报告 ──
    print_report(all_stats)


if __name__ == "__main__":
    main()
