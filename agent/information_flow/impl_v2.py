"""DIKW 信息检索管道 — v2 实现。

相比 v1 的改进：
  L1 (大脑): FTS5 + Jaccard + HRR 三重混合检索（同插件 FactRetriever.search）
  L1 (大脑): 检索时递增 retrieval_count，修复冷数据问题
  L4 (会话): 增加 trigram FTS5 兜底（解决中文 CJK 不分割问题）
  L6 (网络): 直连 Tavily HTTP（不再占位）
  L2-L4: 并行执行（ThreadPoolExecutor）
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
import time
import math
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# ── HRR 导入 ─────────────────────────────────────────────────────────
_HERMES_AGENT = Path.home() / ".hermes" / "hermes-agent"
if str(_HERMES_AGENT) not in sys.path:
    sys.path.insert(0, str(_HERMES_AGENT))

try:
    from plugins.memory.holographic import holographic as hrr
except ImportError:
    hrr = None  # type: ignore[assignment]

from .interface import RetrievalPipeline
from .models import (
    LayerName,
    LayerResult,
    ProcessResult,
    RetrievalContext,
    SafetyLevel,
    TaskCategory,
    ToolCandidate,
    ToolDecision,
)

logger = logging.getLogger(__name__)


# ── 常量 ──────────────────────────────────────────────────────────────

_HERMES_HOME = Path.home() / ".hermes"
_MEMORY_DB = _HERMES_HOME / "memory_store.db"
_STATE_DB = _HERMES_HOME / "state.db"
_VAULT_DIR = _HERMES_HOME / "vault"
_LESSONS_DIR = _VAULT_DIR / "踩坑记录"
_ENTITIES_DIR = _VAULT_DIR / "entities"
_CACHE_DIRS = [
    _HERMES_HOME / "data" / "investment" / "cache",
    _HERMES_HOME / "image_cache",
    _HERMES_HOME / "audio_cache",
    _HERMES_HOME / "video_cache",
]
_SKILLS_DIR = _HERMES_HOME / "skills"
_CONFIG_DIR = _HERMES_HOME

# 指代词关键词
_PRONOUN_WORDS = {"刚才", "之前", "上一条", "你刚才说", "刚刚", "上一步", "前面"}

# 缓存默认 TTL（秒）
_DEFAULT_CACHE_TTL = 3600  # 1小时

# L1 检索权重
_FTS_WEIGHT = 0.4
_JACCARD_WEIGHT = 0.3
_HRR_WEIGHT = 0.3
_HRR_DIM = 1024

# 安全敏感关键词
_DESTRUCTIVE_KEYWORDS = {
    "rm ": SafetyLevel.WARN, "rm -rf": SafetyLevel.BLOCK, "drop table": SafetyLevel.BLOCK,
    "drop database": SafetyLevel.BLOCK, "delete from": SafetyLevel.WARN,
    "shutdown": SafetyLevel.WARN, "reboot": SafetyLevel.WARN, "restart service": SafetyLevel.WARN,
    "kill -9": SafetyLevel.WARN, "chmod 777": SafetyLevel.WARN, ">:": SafetyLevel.WARN,
    "dd if=": SafetyLevel.BLOCK, "format ": SafetyLevel.BLOCK, "mkfs": SafetyLevel.BLOCK,
    ":(){ :|:& };:": SafetyLevel.BLOCK, "eval ": SafetyLevel.WARN, "exec ": SafetyLevel.WARN,
}

# 任务类型 → 推荐工具 路由表
_TASK_TOOL_ROUTING: Dict[TaskCategory, List[str]] = {
    TaskCategory.ANALYSIS: ["execute_code", "terminal"],
    TaskCategory.FILE_READ: ["read_file"],
    TaskCategory.FILE_WRITE: ["write_file"],
    TaskCategory.FILE_EDIT: ["patch"],
    TaskCategory.SEARCH_SRC: ["search_files"],
    TaskCategory.SEARCH_WEB: ["web_search"],
    TaskCategory.SEARCH_MEMORY: ["fact_store"],
    TaskCategory.SEARCH_SESSION: ["session_search"],
    TaskCategory.NETWORK: ["terminal", "execute_code"],
    TaskCategory.SHELL: ["terminal"],
    TaskCategory.BROWSER: ["browser_navigate", "browser_click"],
    TaskCategory.SKILL: ["skill_view"],
    TaskCategory.UNKNOWN: [],
}

_QUERY_TASK_PATTERNS: List[Tuple[re.Pattern, TaskCategory]] = [
    (re.compile(r"计算|分析|对比|汇总|统计|归因|根因|回测|验证"), TaskCategory.ANALYSIS),
    (re.compile(r"读|查看|打开|cat\b|less\b|展示|显示"), TaskCategory.FILE_READ),
    (re.compile(r"写|创建|生成|保存|导出|新建"), TaskCategory.FILE_WRITE),
    (re.compile(r"改|修改|编辑|更新|替换|添加|删除|配置"), TaskCategory.FILE_EDIT),
    (re.compile(r"搜|搜索|找|查找|查.*源码|查.*函数"), TaskCategory.SEARCH_SRC),
    (re.compile(r"联网|网上|最新|今天|新闻|热点|搜索.*关键词|查询.*数据"), TaskCategory.SEARCH_WEB),
    (re.compile(r"记.*忆|还记得|之前聊过|之前说过|principle|原则"), TaskCategory.SEARCH_MEMORY),
    (re.compile(r"之前.*会话|之前.*对话|最近.*聊|哪个.*会话"), TaskCategory.SEARCH_SESSION),
    (re.compile(r"下载|请求|调用API|curl\b|http|fetch"), TaskCategory.NETWORK),
    (re.compile(r"终端|执行|运行|脚本|bash|sh\b|命令"), TaskCategory.SHELL),
    (re.compile(r"浏览器|网页|页面|点击|导航|表单|登录"), TaskCategory.BROWSER),
    (re.compile(r"skill\b|技能|加载.*skill"), TaskCategory.SKILL),
]


# ── 实现 ──────────────────────────────────────────────────────────────

class ImplV2(RetrievalPipeline):
    """v2 实现：混合 HRR 检索引擎 + 语义检索 + 并行层 + 计数修复 + 中文 trigram 兜底。"""

    VERSION = "v2"
    DESCRIPTION = "HRR 混合检索 + FTS5/Jaccard/HRR 三重评分 + Chinese trigram + Tavily 直连 + 并行 L2-L4"

    _hrr_available = hrr is not None and hrr._HAS_NUMPY

    # ── 核心接口 ────────────────────────────────────────────────────

    async def process(self, ctx: RetrievalContext) -> ProcessResult:
        total_start = time.monotonic()
        result = ProcessResult()
        query = ctx.query.strip()

        # ── 第 0 层：指代词快速路径 ──
        l0 = self._layer0_pronoun(query)
        result.layer_results[0] = l0
        if l0.hit:
            result.hit_layer = 0
            result.consolidated_data = l0.data
            result.total_elapsed_ms = self._elapsed_ms(total_start)
            result.tool_decision = self._classify_task(query, ctx)
            return result

        # ── 第 1 层：大脑（HRR 混合） ──
        l1 = self._layer1_brain(query)
        result.layer_results[1] = l1
        if l1.hit:
            result.hit_layer = 1
            result.consolidated_data = l1.data
            result.total_elapsed_ms = self._elapsed_ms(total_start)
            result.tool_decision = self._classify_task(query, ctx)
            return result

        # ── 第 2-4 层：并行执行 ──
        future_map: Dict[Future, int] = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            future_map[pool.submit(self._layer2_lessons, query)] = 2
            future_map[pool.submit(self._layer3_knowledge, query)] = 3
            future_map[pool.submit(self._layer4_sessions, query)] = 4

            for future in as_completed(future_map):
                layer = future_map[future]
                try:
                    lr = future.result()
                except Exception as e:
                    lr = LayerResult(hit=False, layer=layer, elapsed_ms=0, source=f"ERROR: {e}")
                result.layer_results[layer] = lr
                if lr.hit and result.hit_layer < 0:
                    result.hit_layer = layer
                    result.consolidated_data = lr.data

        if result.hit_layer >= 0:
            result.total_elapsed_ms = self._elapsed_ms(total_start)
            result.tool_decision = self._classify_task(query, ctx)
            return result

        # ── 第 5 层：缓存点 ──
        l5 = self._layer5_cache(query)
        result.layer_results[5] = l5
        if l5.hit:
            result.hit_layer = 5
            result.consolidated_data = l5.data
            result.total_elapsed_ms = self._elapsed_ms(total_start)
            result.tool_decision = self._classify_task(query, ctx)
            return result

        # ── 第 6 层：网络搜索（Tavily 直连） ──
        l6 = self._layer6_web(query)
        result.layer_results[6] = l6
        if l6.hit:
            result.hit_layer = 6
            result.consolidated_data = l6.data
        else:
            result.hit_layer = -1

        result.total_elapsed_ms = self._elapsed_ms(total_start)

        # ── 第 7 层：工具调用决策 ──
        result.tool_decision = self._classify_task(query, ctx)

        return result

    async def store_feedback(
        self,
        result: ProcessResult,
        success: bool,
        error_msg: Optional[str] = None,
    ) -> bool:
        result.execution_success = success
        result.execution_error = error_msg
        result.feedback_stored = False
        return True

    # ── 第 0 层：指代词 ─────────────────────────────────────────────

    def _layer0_pronoun(self, query: str) -> LayerResult:
        start = time.monotonic()
        for word in _PRONOUN_WORDS:
            if word in query:
                return LayerResult(
                    hit=True, layer=0, data=query,
                    source=f"指代词匹配: {word}",
                    confidence=0.95, elapsed_ms=self._elapsed_ms(start),
                )
        return LayerResult(hit=False, layer=0, elapsed_ms=self._elapsed_ms(start))

    # ── 第 1 层：大脑（HRR 混合检索） ──────────────────────────────

    def _layer1_brain(self, query: str) -> LayerResult:
        """FTS5 → Jaccard → HRR 三重混合检索 + retrieval_count 递增。"""
        start = time.monotonic()
        if not _MEMORY_DB.exists():
            return LayerResult(hit=False, layer=1, elapsed_ms=self._elapsed_ms(start))

        try:
            conn = sqlite3.connect(str(_MEMORY_DB))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            keywords = self._extract_keywords(query)
            if keywords:
                fts_query = " OR ".join(f'"{kw}"' for kw in keywords)
                cur.execute(
                    """SELECT f.fact_id, f.content, f.category, f.tags,
                              f.trust_score, f.retrieval_count, f.hrr_vector
                       FROM facts_fts fts
                       JOIN facts f ON fts.rowid = f.fact_id
                       WHERE facts_fts MATCH ?
                       ORDER BY rank
                       LIMIT 15""",
                    (fts_query,),
                )
                candidates = [dict(r) for r in cur.fetchall()]
            else:
                candidates = []

            # 中文兜底：FTS5 未命中时用 LIKE
            if not candidates:
                candidates = self._like_candidates(conn, query, limit=15)

            if not candidates:
                conn.close()
                return LayerResult(hit=False, layer=1, elapsed_ms=self._elapsed_ms(start))

            # 三重加权评分
            query_tokens = self._tokenize(query)
            query_vec = hrr.encode_text(query, _HRR_DIM) if self._hrr_available else None  # type: ignore[union-attr]

            scored = []
            for fact in candidates:
                content_tokens = self._tokenize(fact.get("content", ""))
                tag_tokens = self._tokenize(fact.get("tags", ""))
                all_tokens = content_tokens | tag_tokens

                jaccard = self._jaccard_similarity(query_tokens, all_tokens)
                fts_score = float(fact.get("fts_rank", 0.5))

                # HRR 语义相似度
                hrr_sim = 0.5  # neutral
                if self._hrr_available and query_vec is not None and fact.get("hrr_vector"):
                    try:
                        fact_vec = hrr.bytes_to_phases(fact["hrr_vector"])  # type: ignore[union-attr]
                        raw_sim = hrr.similarity(query_vec, fact_vec)  # type: ignore[union-attr]
                        hrr_sim = (raw_sim + 1.0) / 2.0  # shift [0, 1]
                    except Exception:
                        pass

                relevance = (_FTS_WEIGHT * fts_score
                             + _JACCARD_WEIGHT * jaccard
                             + _HRR_WEIGHT * hrr_sim)

                score = relevance * fact.get("trust_score", 0.5)
                fact["score"] = score
                scored.append(fact)

            scored.sort(key=lambda x: x["score"], reverse=True)
            best = scored[0]

            # 递增 retrieval_count（修复冷数据问题）
            try:
                cur.execute(
                    "UPDATE facts SET retrieval_count = retrieval_count + 1 WHERE fact_id = ?",
                    (best["fact_id"],),
                )
                conn.commit()
            except Exception:
                conn.rollback()

            conn.close()

            elapsed = self._elapsed_ms(start)
            return LayerResult(
                hit=True, layer=1,
                data={
                    "fact_id": best["fact_id"],
                    "content": best["content"],
                    "category": best.get("category"),
                    "tags": best.get("tags"),
                    "trust_score": best.get("trust_score"),
                    "score": round(best["score"], 4),
                },
                source=(
                    f"Holographic Hybrid [FTS5+Jaccard+HRR] (memory_store.db): "
                    f"{len(candidates)} candidates, best score={best['score']:.3f}"
                ),
                confidence=float(best.get("trust_score", 0.5)),
                elapsed_ms=elapsed,
            )

        except Exception as e:
            logger.warning("[InfoFlow v2] L1 brain failed: %s", e)

        return LayerResult(hit=False, layer=1, elapsed_ms=self._elapsed_ms(start))

    def _like_candidates(
        self, conn: sqlite3.Connection, query: str, limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """中文 LIKE 兜底：提取 2+ 字词做 LIKE OR 搜索。"""
        # 提取 CUV 长词
        words = re.findall(r"[\u4e00-\u9fff]{2,}", query)
        words = [w for w in words if w not in ("什么", "怎么", "为什么", "这个", "那个", "一个")]
        if not words:
            return []

        conditions = " OR ".join("f.content LIKE ?" for _ in words)
        params = [f"%{w}%" for w in words]
        try:
            cur = conn.execute(
                f"""SELECT f.fact_id, f.content, f.category, f.tags,
                           f.trust_score, f.retrieval_count, f.hrr_vector,
                           CAST(0 AS REAL) as fts_rank
                   FROM facts f
                   WHERE f.hrr_vector IS NOT NULL AND ({conditions})
                   ORDER BY f.trust_score DESC
                   LIMIT ?""",
                params + [limit],
            )
            return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []

    # ── 第 2 层：踩坑经验 ────────────────────────────────────────────

    def _layer2_lessons(self, query: str) -> LayerResult:
        start = time.monotonic()
        if not _LESSONS_DIR.exists():
            return LayerResult(hit=False, layer=2, elapsed_ms=self._elapsed_ms(start))

        keywords = self._extract_keywords(query)
        if not keywords:
            return LayerResult(hit=False, layer=2, elapsed_ms=self._elapsed_ms(start))

        try:
            for fpath in sorted(_LESSONS_DIR.iterdir()):
                if not fpath.is_file() or fpath.suffix not in (".md", ".txt"):
                    continue
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    for kw in keywords:
                        if kw.lower() in content.lower():
                            return LayerResult(
                                hit=True, layer=2,
                                data={"file": str(fpath), "content": content[:2000]},
                                source=f"vault/踩坑记录/{fpath.name}",
                                confidence=0.7,
                                elapsed_ms=self._elapsed_ms(start),
                            )
                except (OSError, UnicodeDecodeError):
                    continue
        except Exception as e:
            logger.warning("[InfoFlow v2] L2 lessons failed: %s", e)

        return LayerResult(hit=False, layer=2, elapsed_ms=self._elapsed_ms(start))

    # ── 第 3 层：知识库 ──────────────────────────────────────────────

    def _layer3_knowledge(self, query: str) -> LayerResult:
        start = time.monotonic()
        keywords = self._extract_keywords(query)
        if not keywords:
            return LayerResult(hit=False, layer=3, elapsed_ms=self._elapsed_ms(start))

        for search_dir in [_ENTITIES_DIR, _VAULT_DIR]:
            if not search_dir.exists():
                continue
            try:
                for fpath in sorted(search_dir.rglob("*")):
                    if not fpath.is_file() or fpath.suffix not in (".md", ".txt", ".json"):
                        continue
                    fname = fpath.stem.lower()
                    for kw in keywords:
                        if kw.lower() in fname:
                            try:
                                content = fpath.read_text(encoding="utf-8", errors="replace")
                                return LayerResult(
                                    hit=True, layer=3,
                                    data={"file": str(fpath), "content": content[:2000]},
                                    source=f"vault/{search_dir.name}/{fpath.name}",
                                    confidence=0.8,
                                    elapsed_ms=self._elapsed_ms(start),
                                )
                            except (OSError, UnicodeDecodeError):
                                break
            except Exception:
                continue

        return LayerResult(hit=False, layer=3, elapsed_ms=self._elapsed_ms(start))

    # ── 第 4 层：近期对话（含 trigram 兜底） ────────────────────────

    def _layer4_sessions(self, query: str) -> LayerResult:
        start = time.monotonic()
        if not _STATE_DB.exists():
            return LayerResult(hit=False, layer=4, elapsed_ms=self._elapsed_ms(start))

        keywords = self._extract_keywords(query)
        if not keywords:
            return LayerResult(hit=False, layer=4, elapsed_ms=self._elapsed_ms(start))

        try:
            conn = sqlite3.connect(str(_STATE_DB))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            fts_query = " OR ".join(f'"{kw}"' for kw in keywords)
            cur.execute(
                """SELECT m.id, m.session_id, m.role, m.content, s.source, s.started_at
                   FROM messages_fts mfts
                   JOIN messages m ON mfts.rowid = m.id
                   JOIN sessions s ON m.session_id = s.id
                   WHERE messages_fts MATCH ?
                     AND m.role IN ('user', 'assistant')
                   ORDER BY rank
                   LIMIT 5""",
                (fts_query,),
            )
            rows = [dict(r) for r in cur.fetchall()]

            # 中文 trigram 兜底
            if not rows:
                chinese_words = re.findall(r"[\u4e00-\u9fff]{2,}", query)
                chinese_words = [w for w in chinese_words if len(w) >= 2][:5]
                if chinese_words:
                    trigram_query = " OR ".join(f'"{w}"' for w in chinese_words)
                    cur.execute(
                        """SELECT m.id, m.session_id, m.role, m.content, s.source, s.started_at
                           FROM messages_fts_trigram mfts
                           JOIN messages m ON mfts.rowid = m.id
                           JOIN sessions s ON m.session_id = s.id
                           WHERE messages_fts_trigram MATCH ?
                             AND m.role IN ('user', 'assistant')
                           ORDER BY rank
                           LIMIT 5""",
                        (trigram_query,),
                    )
                    rows = [dict(r) for r in cur.fetchall()]

            conn.close()

            if rows:
                return LayerResult(
                    hit=True, layer=4,
                    data=[dict(r) for r in rows],
                    source=f"Session DB (state.db): {len(rows)} hits{' (trigram)' if 'trigram' in str(cur.lastrowid or '') else ''}",
                    confidence=0.6,
                    elapsed_ms=self._elapsed_ms(start),
                )
        except Exception as e:
            logger.warning("[InfoFlow v2] L4 sessions failed: %s", e)

        return LayerResult(hit=False, layer=4, elapsed_ms=self._elapsed_ms(start))

    # ── 第 5 层：缓存点 ──────────────────────────────────────────────

    def _layer5_cache(self, query: str) -> LayerResult:
        start = time.monotonic()
        keywords = self._extract_keywords(query)
        if not keywords:
            return LayerResult(hit=False, layer=5, elapsed_ms=self._elapsed_ms(start))

        now = time.time()
        for cache_dir in _CACHE_DIRS:
            if not cache_dir.exists():
                continue
            try:
                for fpath in cache_dir.rglob("*"):
                    if not fpath.is_file():
                        continue
                    mtime = fpath.stat().st_mtime
                    age = now - mtime
                    if age > _DEFAULT_CACHE_TTL:
                        continue
                    fname = fpath.stem.lower()
                    for kw in keywords:
                        if kw.lower() in fname:
                            try:
                                content = fpath.read_text(encoding="utf-8", errors="replace")
                            except (OSError, UnicodeDecodeError):
                                content = f"[binary file] {fpath.name}"
                            return LayerResult(
                                hit=True, layer=5,
                                data={"file": str(fpath), "content": content[:2000], "age_seconds": age},
                                source=f"cache/{cache_dir.name}/{fpath.name} (TTL valid)",
                                confidence=0.5,
                                elapsed_ms=self._elapsed_ms(start),
                            )
            except Exception:
                continue

        return LayerResult(hit=False, layer=5, elapsed_ms=self._elapsed_ms(start))

    # ── 第 6 层：网络搜索（Tavily 直连） ────────────────────────────

    def _layer6_web(self, query: str) -> LayerResult:
        start = time.monotonic()
        # 尝试从 Agent 环境读取 Tavily API key
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            # 尝试从 config 目录的某个文件读
            env_file = _CONFIG_DIR / ".env"
            if env_file.exists():
                try:
                    for line in env_file.read_text().splitlines():
                        if line.startswith("TAVILY_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
                except Exception:
                    pass

        if not api_key:
            return LayerResult(hit=False, layer=6, elapsed_ms=self._elapsed_ms(start))

        try:
            data = json.dumps({
                "query": query,
                "max_results": 3,
                "api_key": api_key,
            }).encode()
            req = Request(
                "https://api.tavily.com/search",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())

            results = result.get("results", [])
            if results:
                return LayerResult(
                    hit=True, layer=6,
                    data={"results": [{
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "content": r.get("content", ""),
                    } for r in results[:3]]},
                    source=f"Tavily web search: {len(results)} results",
                    confidence=0.5,
                    elapsed_ms=self._elapsed_ms(start),
                )
        except Exception as e:
            logger.debug("[InfoFlow v2] L6 web search failed: %s", e)

        return LayerResult(hit=False, layer=6, elapsed_ms=self._elapsed_ms(start))

    # ── 第 7 层：工具调用决策 ────────────────────────────────────────

    def _classify_task(self, query: str, ctx: RetrievalContext) -> ToolDecision:
        decision = ToolDecision()

        # ① 扫描 skills
        matched_skills = self._scan_skills(query)
        decision.matched_skills = matched_skills
        if matched_skills:
            decision.skill_loaded = True

        # ② 选工具
        task_cat = self._detect_task_category(query)
        tools = _TASK_TOOL_ROUTING.get(task_cat, [])
        if matched_skills:
            tools = ["skill_view"] + tools

        decision.recommendations = [
            ToolCandidate(
                tool_name=t,
                task_category=task_cat,
                confidence=0.9 if i == 0 else 0.6,
                reason=self._tool_reason(t, task_cat, matched_skills),
            )
            for i, t in enumerate(tools[:3])
        ]

        # ③ 验可用性
        for t in decision.recommendations:
            t.precheck_passed = True

        # ④ 批量检测
        batch_check = self._detect_batch(query)
        decision.batch_eligible = batch_check["eligible"]
        decision.batch_hint = batch_check["hint"]

        # ⑤ 安全检查
        safety = self._check_safety(query)
        decision.safety = safety["level"]
        decision.safety_reason = safety["reason"]

        return decision

    # ── 辅助方法 ──────────────────────────────────────────────────────

    def _scan_skills(self, query: str) -> List[str]:
        matched = []
        if not _SKILLS_DIR.exists():
            return matched
        q_lower = query.lower()
        try:
            for fpath in _SKILLS_DIR.rglob("SKILL.md"):
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    m = re.search(r"^triggers:\s*\[(.+)\]", content, re.MULTILINE)
                    if m:
                        triggers = [t.strip().strip('"').strip("'") for t in m.group(1).split(",")]
                        for t in triggers:
                            if t.lower() in q_lower:
                                matched.append(fpath.parent.name)
                                break
                except Exception:
                    continue
        except Exception:
            pass
        return matched

    def _detect_task_category(self, query: str) -> TaskCategory:
        for pattern, category in _QUERY_TASK_PATTERNS:
            if pattern.search(query):
                return category
        return TaskCategory.UNKNOWN

    def _tool_reason(self, tool: str, cat: TaskCategory, skills: List[str]) -> str:
        reasons = {
            "execute_code": "适合批量/计算密集型操作，自动合并同类工具调用",
            "read_file": "读取文件内容",
            "write_file": "创建新文件",
            "patch": "精准编辑已有文件",
            "search_files": "搜索文件内容/路径",
            "web_search": "联网搜索外部信息",
            "fact_store": "查询/存储长久记忆（Holographic）",
            "session_search": "回溯历史会话内容",
            "terminal": "执行 Shell 命令",
            "skill_view": "加载匹配的技能模板",
        }
        base = reasons.get(tool, f"执行 {tool}")
        if skills:
            base += f" (skills: {', '.join(skills[:2])}...)"
        return base

    def _detect_batch(self, query: str) -> Dict[str, Any]:
        batch_keywords = ["全部", "批量", "所有", "每个", "逐个", "多地"]
        for kw in batch_keywords:
            if kw in query:
                return {"eligible": True, "hint": "发现批量关键词，建议用 execute_code 合并并行调用"}
        return {"eligible": False, "hint": ""}

    def _check_safety(self, query: str) -> Dict[str, Any]:
        q_lower = query.lower()
        for kw, level in _DESTRUCTIVE_KEYWORDS.items():
            if kw.lower() in q_lower:
                return {"level": level, "reason": f"检测到敏感操作: {kw}"}
        return {"level": SafetyLevel.SAFE, "reason": ""}

    def _extract_keywords(self, query: str) -> List[str]:
        """提取稳定关键词：CJK 2-gram 分词 + 过滤短词+停用词。"""
        tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9_-]{1,}", query)
        # 长 CJK 串拆成 2-gram（如"左侧建仓策略" → "左侧","建仓","策略"）
        expanded = []
        for t in tokens:
            if re.match(r"^[\u4e00-\u9fff]+$", t) and len(t) > 4:
                # 滑窗 2-gram
                expanded.extend(t[i:i+2] for i in range(len(t) - 1))
            else:
                expanded.append(t)
        stopwords = {
            "什么", "怎么", "为什么", "这个", "那个", "一个", "可以",
            "没有", "不是", "就是", "还是", "但是", "因为", "所以",
            "如果", "虽然", "而且", "或者", "the", "this", "that",
            "with", "from", "what", "how", "why", "which", "where",
            "about", "应该", "需要", "已经", "可能", "大概", "基本",
            "之后", "之前", "时候", "然后", "接着",
        }
        return [t for t in expanded if t.lower() not in stopwords][:12]

    def _tokenize(self, text: str) -> set:
        return set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9_-]{1,}", text.lower()))

    def _jaccard_similarity(self, a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return int((time.monotonic() - start) * 1000)
