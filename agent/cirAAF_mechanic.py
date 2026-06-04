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
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ── Constants ──────────────────────────────────────────────────────────────

import os
DB_PATH = Path(os.environ.get("HOLOGRAPHIC_DB_PATH", str(Path.home() / ".hermes" / "memory_store.db")))
REPORT_DIR = Path(os.environ.get("HOLOGRAPHIC_REPORT_DIR", str(Path.home() / ".hermes" / "data" / "cirAAF")))

# ── 自动领域发现配置（v2.2 改造：零配置，按 Holographic 实际数据聚类）─────────
DOMAIN_CACHE_PATH = Path(os.environ.get("HOLOGRAPHIC_REPORT_DIR", str(Path.home() / ".hermes" / "data" / "cirAAF"))) / "domain_cache.json"
MIN_CLUSTER_SIZE = 5            # 聚类最小 fact 数（小于此数的散点合并到 misc）
MAX_CLUSTERS = 15               # 最多聚类数（超过按 fact 数取 top N + 溢出合并 misc）
SIMILARITY_THRESHOLD = 0.18     # Jaccard 相似度阈值（经验值，0.15-0.25 平衡点）
TOP_CANDIDATES = 200            # 倒排索引候选 top N（控制 O(n×N) 计算量）
RECACHE_IF_FACTS_GREW_BY = 0.20 # fact 总数增长超 20% 触发强制重发现
STOP_KEYWORDS = {                # 聚类命名停用词
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "this", "that",
    "these", "those", "it", "its", "和", "的", "是", "在", "了", "与", "或", "也", "但", "就", "都",
}


def extract_features(fact: dict) -> set:
    """从一条 fact 提取特征集（中文 2-gram + 英文单词 + tags + category）

    设计要点：
    - 中文 2-gram 防 FTS5 不分词问题（"PE"是单字会被 FTS5 跳过，2-gram 才能抓住"投资PE"）
    - 保留 tags 和 category 作为强特征（高信息量）
    """
    content = fact.get("content", "") or ""
    tags_str = fact.get("tags", "") or ""
    category = fact.get("category", "") or ""

    # 中文 2-gram
    cjk_segs = re.findall(r"[\u4e00-\u9fff]+", content)
    bigrams = set()
    for seg in cjk_segs:
        if len(seg) >= 2:
            for i in range(len(seg) - 1):
                bigrams.add(seg[i:i + 2])

    # 英文/数字单词（≥2 字符）
    words = set(re.findall(r"[a-zA-Z_][a-zA-Z_0-9]+", content))

    # tags
    tag_set = {t.strip() for t in tags_str.split(",") if t.strip()}

    feats = bigrams | words | tag_set
    if category:
        feats.add(category)
    return feats


def jaccard(set_a: set, set_b: set) -> float:
    """Jaccard 相似度 = |A∩B| / |A∪B|"""
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def auto_discover_domains(conn: sqlite3.Connection) -> dict[str, dict]:
    """
    自动从 Holographic 聚类出 N 个"自然领域"（v2.2 零配置核心）

    算法 4 步：
      ① 拉所有 trust > 0.3 的 fact（排除已降权垃圾）
      ② 提取 2-gram 特征
      ③ 倒排索引 + 贪心连通子图聚类（O(n × TOP_CANDIDATES) ≈ 1.5M 次比较/7774 facts）
      ④ Top 3 关键词拼接命名（v2.3+ 可接 LLM 命名）

    返回结构兼容原 DOMAINS：
      {
        "投资-PE+动量+止盈": {
          "members": [1, 2, 3, ...],        # fact_id 列表（替代 categories）
          "fact_count": 234,
          "avg_trust": 0.65,
          "zero_retrieval_rate": 0.45,
          "health": 56,
          "top_keywords": ["PE", "动量", "止盈", "基金", "估值"],
        },
        ...
      }
    """
    # ① 拉 fact
    cur = conn.execute(
        "SELECT fact_id, content, category, tags, trust_score, retrieval_count "
        "FROM facts WHERE trust_score > 0.3"
    )
    facts = [dict(r) for r in cur]
    if len(facts) < MIN_CLUSTER_SIZE:
        return {"misc": {
            "members": [f["fact_id"] for f in facts],
            "fact_count": len(facts),
            "top_keywords": [],
            "health": 0,
        }}

    # ② 特征提取
    features: dict[int, set] = {}
    for f in facts:
        feats = extract_features(f)
        if feats:
            features[f["fact_id"]] = feats
    if not features:
        return {"misc": {"members": [], "fact_count": 0, "top_keywords": [], "health": 0}}

    # ③ 倒排索引
    inverted: dict[str, set] = {}
    for fid, feats in features.items():
        for f in feats:
            inverted.setdefault(f, set()).add(fid)

    # ④ 贪心聚类（hub 节点优先：高连接度 fact 先开聚类）
    fact_freq = {
        fid: sum(len(inverted.get(feat, set())) for feat in feats)
        for fid, feats in features.items()
    }
    sorted_fids = sorted(features.keys(), key=lambda fid: -fact_freq.get(fid, 0))

    clusters: list[set] = []
    visited: set = set()

    for fid in sorted_fids:
        if fid in visited:
            continue
        target_feats = features[fid]
        # 找 top 候选
        candidate_count: Counter = Counter()
        for f in target_feats:
            for other_fid in inverted.get(f, set()):
                if other_fid != fid:
                    candidate_count[other_fid] += 1
        # 算 Jaccard（top TOP_CANDIDATES 候选）
        cluster = {fid}
        for other_fid, intersect in candidate_count.most_common(TOP_CANDIDATES):
            if other_fid in visited:
                continue
            other_feats = features[other_fid]
            union_size = len(target_feats) + len(other_feats) - intersect
            sim = intersect / union_size if union_size > 0 else 0
            if sim >= SIMILARITY_THRESHOLD:
                cluster.add(other_fid)
        if len(cluster) >= MIN_CLUSTER_SIZE:
            clusters.append(cluster)
            visited |= cluster
        else:
            visited.add(fid)  # 散点不开新聚类，留给 misc 收容

    # ⑤ 散点合并到 misc
    big_clusters = [c for c in clusters if len(c) >= MIN_CLUSTER_SIZE]
    misc = set()
    for c in clusters:
        if len(c) < MIN_CLUSTER_SIZE:
            misc |= c
    # 散点 fact（从未被任何聚类收容的）
    for fid in features:
        if fid not in visited:
            misc.add(fid)
    if misc:
        big_clusters.append(misc)

    # ⑥ 限制聚类数（按 fact 数取 top MAX_CLUSTERS，溢出合并到 misc）
    big_clusters.sort(key=lambda c: -len(c))
    if len(big_clusters) > MAX_CLUSTERS:
        top_clusters = big_clusters[:MAX_CLUSTERS - 1]
        overflow = set()
        for c in big_clusters[MAX_CLUSTERS - 1:]:
            overflow |= c
        if overflow:
            top_clusters.append(overflow)
        big_clusters = top_clusters

    # ⑦ 命名 + 健康分
    domains: dict[str, dict] = {}
    fact_id_to_data = {f["fact_id"]: f for f in facts}

    for i, cluster in enumerate(big_clusters):
        # 统计 top 5 关键词
        kw_counter: Counter = Counter()
        for fid in cluster:
            for f in features.get(fid, []):
                kw_counter[f] += 1
        for stop in STOP_KEYWORDS:
            kw_counter.pop(stop, None)
        top_keywords = [k for k, _ in kw_counter.most_common(5)]

        # 命名（前 3 关键词拼接；不足 3 个用 cluster_N 兜底）
        if len(top_keywords) >= 3:
            name = "+".join(top_keywords[:3])
        elif top_keywords:
            name = "+".join(top_keywords)
        else:
            name = f"cluster_{i}"

        # 健康分
        members_data = [fact_id_to_data[fid] for fid in cluster if fid in fact_id_to_data]
        if not members_data:
            continue
        avg_trust = sum(m["trust_score"] for m in members_data) / len(members_data)
        zero_ret = sum(1 for m in members_data if (m.get("retrieval_count") or 0) == 0)
        zero_ret_rate = zero_ret / len(members_data)
        health = int(avg_trust * (1 - zero_ret_rate) * 100)

        domains[name] = {
            "members": [m["fact_id"] for m in members_data],
            "fact_count": len(members_data),
            "avg_trust": round(avg_trust, 3),
            "zero_retrieval_rate": round(zero_ret_rate, 3),
            "health": health,
            "top_keywords": top_keywords,
        }

    return domains


def load_or_discover_domains(conn: sqlite3.Connection, force_rediscover: bool = False) -> dict:
    """
    带缓存的自动聚类（主入口）

    - 缓存存在 + 不强制重发现 + fact 增长 < 20% → 直接读缓存
    - 否则跑 auto_discover_domains() + 写缓存

    缓存位置：~/.hermes/data/cirAAF/domain_cache.json
    """
    DOMAIN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not force_rediscover and DOMAIN_CACHE_PATH.exists():
        try:
            cache = json.loads(DOMAIN_CACHE_PATH.read_text(encoding="utf-8"))
            cur = conn.execute("SELECT COUNT(*) FROM facts")
            current_count = cur.fetchone()[0]
            cached_count = cache.get("fact_count_at_cache", 0)
            grew = (current_count - cached_count) / max(cached_count, 1)
            if grew < RECACHE_IF_FACTS_GREW_BY:
                return cache["domains"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # 缓存损坏，重发现

    domains = auto_discover_domains(conn)

    cur = conn.execute("SELECT COUNT(*) FROM facts")
    fact_count = cur.fetchone()[0]
    cache = {
        "discovered_at": datetime.now().isoformat(),
        "fact_count_at_cache": fact_count,
        "config": {
            "MIN_CLUSTER_SIZE": MIN_CLUSTER_SIZE,
            "MAX_CLUSTERS": MAX_CLUSTERS,
            "SIMILARITY_THRESHOLD": SIMILARITY_THRESHOLD,
        },
        "domains": domains,
    }
    DOMAIN_CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return domains

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
    """扫描单个领域的健康指标（v2.2 改造：按 fact_id members 过滤）"""
    members = cfg.get("members", [])
    placeholders = ",".join("?" for _ in members) if members else "NULL"
    # 兜底 refactored_tag（v2.2 聚类名带关键词，不一定匹配旧硬编码 tag）
    refactored_tag = cfg.get("refactored_tag", f"refactored:{domain}")

    # 该领域总事实数
    cur = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE fact_id IN ({placeholders})",
        members,
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
        FROM facts WHERE fact_id IN ({placeholders})""",
        members,
    )
    stats = dict(cur.fetchone())

    # 零检索事实
    cur = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE fact_id IN ({placeholders}) AND retrieval_count = 0",
        members,
    )
    zero_retrieval = cur.fetchone()[0]

    # 已标记 refactored 的事实（v2.2 兜底：tag 名可能含聚类关键词而非硬编码）
    cur = conn.execute(
        "SELECT COUNT(*) FROM facts WHERE fact_id IN (" + placeholders + ") AND tags LIKE ?",
        members + [f"%{refactored_tag}%"],
    )
    refactored_count = cur.fetchone()[0]

    # 最近 refactored 时间
    cur = conn.execute(
        f"""SELECT updated_at FROM facts
            WHERE fact_id IN ({placeholders}) AND tags LIKE ?
            ORDER BY updated_at DESC LIMIT 1""",
        members + [f"%{refactored_tag}%"],
    )
    row = cur.fetchone()
    last_refactored = row["updated_at"] if row else "never"

    # 健康分 (0-100)
    health = cfg.get("health", _compute_health(total, stats["avg_trust"] or 0.5, zero_retrieval, total))

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
        "priority": cfg.get("priority", "auto"),  # v2.2 兜底：聚类无 priority
        "max_age_days": cfg.get("max_age_days", 30),  # v2.2 兜底：聚类无 max_age_days
        "top_keywords": cfg.get("top_keywords", []),  # v2.2 新增：聚类关键词
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
    判断一个领域是否达到衰减条件（v2.2 改造：按 fact_id members 过滤）。
    返回 (ready, reason)。
    """
    members = cfg.get("members", [])
    ph = ",".join("?" for _ in members) if members else "NULL"

    # 条件1：至少有5条事实 trust > 0.7（表明模型手动升权形成了分层）
    cur = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE fact_id IN ({ph}) AND trust_score > 0.7",
        members,
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
        f"SELECT created_at FROM facts WHERE fact_id IN ({ph}) ORDER BY created_at ASC",
        members,
    )
    ages = [r[0] for r in cur.fetchall()]
    if not ages:
        return False, "领域无事实"

    mid_idx = len(ages) // 2
    median_age_str = ages[mid_idx]
    median_age_days = (datetime.now() - datetime.fromisoformat(median_age_str)).days
    threshold_days = max(14, int(median_age_days * 1.5))

    cur = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE fact_id IN ({ph}) AND created_at < ?",
        members + [since(threshold_days)],
    )
    old_count = cur.fetchone()[0]
    if old_count < 5:
        return False, f"超过中位年龄1.5倍({threshold_days}天)的事实仅{old_count}条，目标太少"

    return True, f"三条件均满足：高信任{high_trust_count}条 + 停滞{recent[-1]['health']}分不变 + 年龄阈值{threshold_days}天"


def apply_decay(dry_run: bool = True) -> list[dict]:
    """应用机械衰减规则，返回操作记录（v2.2 改造：基于自动聚类）"""
    conn = get_db()
    thresholds = _compute_decay_thresholds(conn)
    history = _load_health_history()

    # v2.2 改造：用 load_or_discover_domains() 替代硬编码 DOMAINS
    domains = load_or_discover_domains(conn)

    # 替换旧版年龄守卫：改为每领域独立判断三条件
    # 先扫描所有领域健康状态（复用 scan_domain）
    domain_ready: dict[str, str] = {}
    all_stats = []
    for domain, cfg in domains.items():
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

    # 只对满足条件的领域执行衰减（v2.2 改造：members 是 fact_id 列表）
    ready_members: list[int] = []
    for domain in ready_domains:
        ready_members.extend(domains[domain].get("members", []))
    ready_ph = ",".join("?" for _ in ready_members) if ready_members else "NULL"

    for rule_name, rule in DECAY_RULES.items():
        params = ready_members.copy()
        if "age_key" in rule:
            params.append(since(thresholds[rule["age_key"]]))
        elif rule.get("age_days", 0) > 0:
            params.append(since(rule["age_days"]))

        # v2.2 改造：按 fact_id 过滤
        condition_with_domain = f"fact_id IN ({ready_ph}) AND {rule['condition']}"
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
    """生成供 LLM cron 使用的反射数据包（v2.2 改造：基于自动聚类）"""
    conn = get_db()
    domains = load_or_discover_domains(conn)

    package = {
        "generated_at": datetime.now().isoformat(),
        "mode": "full" if not domain else f"single:{domain}",
        "domains": {},
    }

    targets = [domain] if domain else list(domains.keys())
    for d in targets:
        if d not in domains:
            continue
        cfg = domains[d]
        members = cfg.get("members", [])
        placeholders = ",".join("?" for _ in members) if members else "NULL"

        # 收集所有该领域事实
        cur = conn.execute(
            f"""SELECT fact_id, content, category, tags, trust_score,
                       retrieval_count, helpful_count, created_at, updated_at
                FROM facts WHERE fact_id IN ({placeholders})
                ORDER BY trust_score ASC LIMIT 200""",
            members,
        )
        facts = [dict(r) for r in cur.fetchall()]

        # 统计指标
        cur = conn.execute(
            f"SELECT COUNT(*) FROM facts WHERE fact_id IN ({placeholders}) AND trust_score < 0.5",
            members,
        )
        low_trust_count = cur.fetchone()[0]

        cur = conn.execute(
            f"SELECT COUNT(*) FROM facts WHERE fact_id IN ({placeholders}) AND retrieval_count = 0 AND created_at < ?",
            members + [since(30)],
        )
        stale_count = cur.fetchone()[0]

        package["domains"][d] = {
            "config": {k: v for k, v in cfg.items() if k != "members"},
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
    parser = argparse.ArgumentParser(description="CIRAAF 大脑机械引擎（v2.2 零配置自动聚类）")
    parser.add_argument("--decay", action="store_true", help="执行机械衰减（dry-run 默认）")
    parser.add_argument("--apply", action="store_true", help="配合 --decay 实际执行")
    parser.add_argument("--domain", type=str, help="单领域详细扫描（聚类名，如 '投资-PE+动量+止盈'）")
    parser.add_argument("--refactor-report", action="store_true", help="生成 Gear 2 反射数据包")
    parser.add_argument("--apply-refactor", type=str, help="应用 Gear 2 修复指令（JSON 文件路径）")
    parser.add_argument("--rediscover", action="store_true", help="v2.2 强制重发现领域（忽略缓存）")
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

    # ── 全领域扫描（v2.2 改造：先 load_or_discover_domains） ──
    conn = get_db()
    domains = load_or_discover_domains(conn, force_rediscover=args.rediscover)
    all_stats = []
    for domain, cfg in domains.items():
        if args.domain and domain != args.domain:
            continue
        stats = scan_domain(conn, domain, cfg)
        all_stats.append(stats)
    conn.close()

    # ── 单领域详细扫描（v2.2 改造：找不到领域时友好提示） ──
    if args.domain:
        if not all_stats:
            print(f"\n❌ 错误：领域 '{args.domain}' 不存在")
            print(f"   可用领域（自动聚类）: {list(domains.keys())[:10]}")
            print(f"   提示：用默认报告看真实领域名（不是 --domain 传硬编码）")
            conn.close()
            sys.exit(1)
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
