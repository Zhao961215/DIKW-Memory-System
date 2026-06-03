#!/usr/bin/env python3
"""information_flow 管道健康检查 — 每周收集统计数据。
输出 JSON 供 cron LLM 分析是否需要升级到 v2。"""

import json, os, sqlite3, time
from pathlib import Path

HERMES_HOME = Path.home() / ".hermes"
MEMORY_DB = HERMES_HOME / "memory_store.db"
STATE_DB = HERMES_HOME / "state.db"
SKILLS_DIR = HERMES_HOME / "skills"
LESSONS_DIR = HERMES_HOME / "data" / "knowledge" / "vault" / "踩坑记录"

report = {"timestamp": time.strftime("%Y-%m-%d %H:%M"), "checks": {}}

# ── 1. 模块完整性 ──
module_ok = (
    (HERMES_HOME / "hermes-agent" / "agent" / "information_flow" / "impl_v1.py").exists()
)
report["checks"]["module_exists"] = module_ok

# ── 2. 记忆库健康 ──
if MEMORY_DB.exists():
    conn = sqlite3.connect(str(MEMORY_DB))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM facts")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM facts WHERE retrieval_count > 0")
    retrieved = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM facts WHERE retrieval_count >= 5")
    hot = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM facts WHERE retrieval_count = 0")
    cold = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM facts f WHERE NOT EXISTS (SELECT 1 FROM facts_fts WHERE rowid = f.fact_id)")
    no_fts = cur.fetchone()[0]

    cur.execute("""
        SELECT AVG(trust_score), MIN(trust_score), MAX(trust_score)
        FROM facts WHERE trust_score IS NOT NULL
    """)
    trust_avg, trust_min, trust_max = cur.fetchone()

    cur.execute("""
        SELECT category, COUNT(*) as cnt
        FROM facts GROUP BY category ORDER BY cnt DESC LIMIT 10
    """)
    cat_dist = dict(cur.fetchall())

    conn.close()

    report["checks"]["memory_db"] = {
        "total_facts": total,
        "retrieved_ever": retrieved,
        "hot_5plus": hot,
        "cold_never": cold,
        "no_fts_index": no_fts,
        "retrieval_rate": round(retrieved / total * 100, 1) if total else 0,
        "trust_avg": round(trust_avg, 2) if trust_avg else 0,
        "trust_min": round(trust_min, 2) if trust_min else 0,
        "trust_max": round(trust_max, 2) if trust_max else 0,
        "categories": cat_dist,
    }
else:
    report["checks"]["memory_db"] = "NOT_FOUND"

# ── 3. 会话库活跃度 ──
if STATE_DB.exists():
    conn = sqlite3.connect(str(STATE_DB))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM sessions")
    total_sessions = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM sessions
        WHERE started_at > datetime('now', '-7 days')
    """)
    weekly_sessions = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM messages WHERE role='assistant'")
    total_msgs = cur.fetchone()[0]

    conn.close()

    report["checks"]["session_db"] = {
        "total_sessions": total_sessions,
        "weekly_active": weekly_sessions,
        "total_messages": total_msgs,
    }
else:
    report["checks"]["session_db"] = "NOT_FOUND"

# ── 4. 踩坑经验库 ──
if LESSONS_DIR.exists():
    lessons = [f.name for f in sorted(LESSONS_DIR.iterdir()) if f.suffix in (".md", ".txt")]
    report["checks"]["lessons"] = {
        "count": len(lessons),
        "files": lessons,
    }
else:
    report["checks"]["lessons"] = {"count": 0, "files": []}

# ── 5. Skill 数量 ──
if SKILLS_DIR.exists():
    skills = [d.name for d in SKILLS_DIR.iterdir() if d.is_dir()]
    report["checks"]["skills_count"] = len(skills)
else:
    report["checks"]["skills_count"] = 0

# ── 6. 升级建议指标 ──
checks = report["checks"]
suggest_upgrade = False
reasons = []

# 检查当前默认版本
v2_already = False
try:
    # 检查 v2 模块是否存在且可导入
    import sys
    sys.path.insert(0, str(HERMES_HOME / "hermes-agent"))
    from agent.information_flow.interface import RetrievalPipeline
    default_ver = RetrievalPipeline.create()
    if default_ver.VERSION == "v2":
        v2_already = True
except Exception:
    pass

# 条件 A：记忆库 > 10000 条 → 需要向量检索提升精度
if isinstance(checks.get("memory_db"), dict):
    if checks["memory_db"]["total_facts"] > 10000:
        suggest_upgrade = True
        reasons.append(f"记忆库 {checks['memory_db']['total_facts']} 条 > 1万，FTS5 精度下降需 HRR")

    # 条件 B：冷数据 > 50% → HRR 可能更好地匹配
    if checks["memory_db"]["cold_never"] > checks["memory_db"]["total_facts"] * 0.5:
        suggest_upgrade = True
        reasons.append(f"冷数据 {checks['memory_db']['cold_never']} 条 > 50%，HRR 语义检索可能提升命中")

# 条件 C：周会话 > 50 → 对话检索量大需要 trigram 模糊搜索
if isinstance(checks.get("session_db"), dict):
    if checks["session_db"]["weekly_active"] > 50:
        suggest_upgrade = True
        reasons.append(f"周活跃 {checks['session_db']['weekly_active']} 会话 > 50，需要 trigram 模糊搜索")

report["upgrade_verdict"] = {
    "suggest": suggest_upgrade,
    "target": "v2" if suggest_upgrade else "v1",
    "reasons": reasons,
}

# 如果 v2 已默认且无新问题，标记为稳定
if v2_already and not suggest_upgrade:
    report["upgrade_verdict"]["status"] = "stable"
    report["upgrade_verdict"]["target"] = "v2(current)"
elif v2_already and suggest_upgrade:
    report["upgrade_verdict"]["status"] = "v2_active_but_needs_more"
elif not v2_already and suggest_upgrade:
    report["upgrade_verdict"]["status"] = "needs_upgrade"

print(json.dumps(report, ensure_ascii=False, indent=2))
