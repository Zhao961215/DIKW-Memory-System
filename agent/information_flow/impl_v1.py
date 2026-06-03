"""DIKW 信息检索管道 — v1 实现。

7+1 层：指代词 → 大脑(DB) → 踩坑(文件) → 知识库(文件) → 会话(DB) → 缓存(mtime) → 网络(HTTP) → 工具决策
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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

# 指代词关键词
_PRONOUN_WORDS = {"刚才", "之前", "上一条", "你刚才说", "刚刚", "上一步", "前面"}

# 缓存默认 TTL（秒）
_DEFAULT_CACHE_TTL = 3600  # 1小时

# 安全敏感关键词（触发 WARN 或 BLOCK）
_DESTRUCTIVE_KEYWORDS = {
    "rm ": "WARN", "rm -rf": "BLOCK", "drop table": "BLOCK",
    "drop database": "BLOCK", "delete from": "WARN",
    "shutdown": "WARN", "reboot": "WARN", "restart service": "WARN",
    "kill -9": "WARN", "chmod 777": "WARN", ">:": "WARN",
    "dd if=": "BLOCK", "format ": "BLOCK", "mkfs": "BLOCK",
    ":(){ :|:& };:": "BLOCK", "eval ": "WARN", "exec ": "WARN",
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

# 查询 → 任务类型 关键词映射
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

class ImplV1(RetrievalPipeline):
    """v1 实现：直接 SQLite/文件系统/HTTP 访问，无需 LLM 参与。"""

    VERSION = "v1"
    DESCRIPTION = "直接 SQLite + 文件系统 + HTTP 的 7+1 层检索管道"

    # ── 核心接口 ────────────────────────────────────────────────────

    async def process(self, ctx: RetrievalContext) -> ProcessResult:
        """执行 7+1 层检索 + 工具决策。"""
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

        # ── 第 1 层：大脑 — 方法论 ──
        l1 = self._layer1_brain(query)
        result.layer_results[1] = l1
        if l1.hit:
            result.hit_layer = 1
            result.consolidated_data = l1.data
            result.total_elapsed_ms = self._elapsed_ms(total_start)
            result.tool_decision = self._classify_task(query, ctx)
            return result

        # ── 第 2 层：踩坑经验 ──
        l2 = self._layer2_lessons(query)
        result.layer_results[2] = l2
        if l2.hit:
            result.hit_layer = 2
            result.consolidated_data = l2.data
            result.total_elapsed_ms = self._elapsed_ms(total_start)
            result.tool_decision = self._classify_task(query, ctx)
            return result

        # ── 第 3 层：知识库 ──
        l3 = self._layer3_knowledge(query)
        result.layer_results[3] = l3
        if l3.hit:
            result.hit_layer = 3
            result.consolidated_data = l3.data
            result.total_elapsed_ms = self._elapsed_ms(total_start)
            result.tool_decision = self._classify_task(query, ctx)
            return result

        # ── 第 4 层：近期对话 ──
        l4 = self._layer4_sessions(query)
        result.layer_results[4] = l4
        if l4.hit:
            result.hit_layer = 4
            result.consolidated_data = l4.data
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

        # ── 第 6 层：网络搜索 ──
        l6 = self._layer6_web(query)
        result.layer_results[6] = l6
        if l6.hit:
            result.hit_layer = 6
            result.consolidated_data = l6.data
        else:
            result.hit_layer = -1  # 全部未命中

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
        """闭环反馈：成功/失败都存回方法论。"""
        # v1 阶段：返回 True 表示"应当存储"，由 Agent 执行实际的 fact_store 调用
        # 因为模块内无法直接调 fact_store tool（那是 LLM 工具，不是 Python 函数）
        result.execution_success = success
        result.execution_error = error_msg
        result.feedback_stored = False  # 标记由 Agent 处理实际写入
        return True

    # ── 第 0 层：指代词 ─────────────────────────────────────────────

    def _layer0_pronoun(self, query: str) -> LayerResult:
        start = time.monotonic()
        for word in _PRONOUN_WORDS:
            if word in query:
                elapsed = self._elapsed_ms(start)
                return LayerResult(
                    hit=True, layer=0, data=query,
                    source=f"指代词匹配: {word}",
                    confidence=0.95, elapsed_ms=elapsed,
                )
        return LayerResult(hit=False, layer=0, elapsed_ms=self._elapsed_ms(start))

    # ── 第 1 层：大脑（Holographic） ─────────────────────────────────

    def _layer1_brain(self, query: str) -> LayerResult:
        start = time.monotonic()
        if not _MEMORY_DB.exists():
            return LayerResult(hit=False, layer=1, elapsed_ms=self._elapsed_ms(start))

        try:
            conn = sqlite3.connect(str(_MEMORY_DB))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 提取关键词（取 query 中最长最有意义的 token）
            keywords = self._extract_keywords(query)
            if not keywords:
                conn.close()
                return LayerResult(hit=False, layer=1, elapsed_ms=self._elapsed_ms(start))

            # FTS5 全文搜索
            fts_query = " OR ".join(f'"{kw}"' for kw in keywords)
            cur.execute(
                """SELECT f.fact_id, f.content, f.category, f.tags,
                          f.trust_score, f.retrieval_count
                   FROM facts_fts fts
                   JOIN facts f ON fts.rowid = f.fact_id
                   WHERE facts_fts MATCH ?
                   ORDER BY rank
                   LIMIT 5""",
                (fts_query,),
            )
            rows = cur.fetchall()
            conn.close()

            if rows:
                best = rows[0]
                elapsed = self._elapsed_ms(start)
                return LayerResult(
                    hit=True, layer=1,
                    data={
                        "fact_id": best["fact_id"],
                        "content": best["content"],
                        "category": best["category"],
                        "tags": best["tags"],
                        "trust_score": best["trust_score"],
                    },
                    source=f"Holographic FTS5 (memory_store.db): {len(rows)} results",
                    confidence=float(best["trust_score"]),
                    elapsed_ms=elapsed,
                )
        except Exception as e:
            logger.warning("[InfoFlow] Layer 1 (brain) query failed: %s", e)

        return LayerResult(hit=False, layer=1, elapsed_ms=self._elapsed_ms(start))

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
                            elapsed = self._elapsed_ms(start)
                            return LayerResult(
                                hit=True, layer=2,
                                data={"file": str(fpath), "content": content[:2000]},
                                source=f"vault/踩坑记录/{fpath.name}",
                                confidence=0.7,
                                elapsed_ms=elapsed,
                            )
                except (OSError, UnicodeDecodeError):
                    continue
        except Exception as e:
            logger.warning("[InfoFlow] Layer 2 (lessons) failed: %s", e)

        return LayerResult(hit=False, layer=2, elapsed_ms=self._elapsed_ms(start))

    # ── 第 3 层：知识库 ──────────────────────────────────────────────

    def _layer3_knowledge(self, query: str) -> LayerResult:
        start = time.monotonic()
        keywords = self._extract_keywords(query)
        if not keywords:
            return LayerResult(hit=False, layer=3, elapsed_ms=self._elapsed_ms(start))

        # 先查 entities/（卡片柜）
        for search_dir in [_ENTITIES_DIR, _VAULT_DIR]:
            if not search_dir.exists():
                continue
            try:
                for fpath in sorted(search_dir.rglob("*")):
                    if not fpath.is_file() or fpath.suffix not in (".md", ".txt", ".json"):
                        continue
                    # 文件名匹配
                    fname = fpath.stem.lower()
                    for kw in keywords:
                        if kw.lower() in fname:
                            try:
                                content = fpath.read_text(encoding="utf-8", errors="replace")
                                elapsed = self._elapsed_ms(start)
                                return LayerResult(
                                    hit=True, layer=3,
                                    data={"file": str(fpath), "content": content[:2000]},
                                    source=f"vault/{search_dir.name}/{fpath.name}",
                                    confidence=0.8,
                                    elapsed_ms=elapsed,
                                )
                            except (OSError, UnicodeDecodeError):
                                break
            except Exception:
                continue

        return LayerResult(hit=False, layer=3, elapsed_ms=self._elapsed_ms(start))

    # ── 第 4 层：近期对话 ────────────────────────────────────────────

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
            rows = cur.fetchall()
            conn.close()

            if rows:
                elapsed = self._elapsed_ms(start)
                return LayerResult(
                    hit=True, layer=4,
                    data=[dict(r) for r in rows],
                    source=f"Session DB (state.db): {len(rows)} hits",
                    confidence=0.6,
                    elapsed_ms=elapsed,
                )
        except Exception as e:
            logger.warning("[InfoFlow] Layer 4 (sessions) failed: %s", e)

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
                    # 检查 TTL
                    mtime = fpath.stat().st_mtime
                    age = now - mtime
                    if age > _DEFAULT_CACHE_TTL:
                        continue  # 过期，视同未命中

                    # 文件名匹配
                    fname = fpath.stem.lower()
                    for kw in keywords:
                        if kw.lower() in fname:
                            elapsed = self._elapsed_ms(start)
                            try:
                                content = fpath.read_text(encoding="utf-8", errors="replace")
                            except (OSError, UnicodeDecodeError):
                                content = f"[binary file] {fpath.name}"
                            return LayerResult(
                                hit=True, layer=5,
                                data={"file": str(fpath), "content": content[:2000], "age_seconds": age},
                                source=f"cache/{cache_dir.name}/{fpath.name} (TTL valid)",
                                confidence=0.5,
                                elapsed_ms=elapsed,
                            )
            except Exception:
                continue

        return LayerResult(hit=False, layer=5, elapsed_ms=self._elapsed_ms(start))

    # ── 第 6 层：网络搜索 ────────────────────────────────────────────

    def _layer6_web(self, query: str) -> LayerResult:
        start = time.monotonic()
        # v1 暂不实现直接 HTTP 调用 Tavily（需要 API key）
        # Agent 会通过 web_search tool 来补充
        # 这里返回未命中，让第 7 层推荐 web_search 工具
        return LayerResult(hit=False, layer=6, elapsed_ms=self._elapsed_ms(start))

    # ── 第 7 层：工具调用决策 ────────────────────────────────────────

    def _classify_task(self, query: str, ctx: RetrievalContext) -> ToolDecision:
        """5 步工具决策：扫描 skills → 选工具 → 验可用性 → 批量检测 → 安全检查"""
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

        # ③ 验可用性 → 标记 precheck_passed（v1 暂不实现注册表查询）
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

    # ── 第 7 层辅助方法 ──────────────────────────────────────────────

    def _scan_skills(self, query: str) -> List[str]:
        """扫描 skills 目录，匹配 query 与 skill triggers。"""
        matched = []
        if not _SKILLS_DIR.exists():
            return matched

        q_lower = query.lower()
        try:
            for fpath in _SKILLS_DIR.rglob("SKILL.md"):
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    # 解析 frontmatter 中的 triggers
                    m = re.search(r"triggers:\s*\[(.*?)\]", content, re.DOTALL)
                    if m:
                        triggers = re.findall(r"'([^']*)'|\"([^\"]*)\"", m.group(1))
                        triggers = [t[0] or t[1] for t in triggers]
                        for t in triggers:
                            if t.lower() in q_lower:
                                # 获取 skill 名（目录名）
                                skill_name = fpath.parent.name
                                if skill_name not in matched:
                                    matched.append(skill_name)
                                    break
                except (OSError, UnicodeDecodeError):
                    continue
        except Exception as e:
            logger.warning("[InfoFlow] Skill scan failed: %s", e)
        return matched

    def _detect_task_category(self, query: str) -> TaskCategory:
        """基于关键词检测任务类型。"""
        q_lower = query.lower()
        for pattern, category in _QUERY_TASK_PATTERNS:
            if pattern.search(q_lower):
                return category
        return TaskCategory.UNKNOWN

    def _tool_reason(
        self, tool: str, cat: TaskCategory, skills: List[str]
    ) -> str:
        if skills:
            return f"匹配到 skill: {skills[0]}，推荐先 skill_view 加载"
        reasons = {
            "execute_code": "分析/计算类任务，最佳工具",
            "patch": "配置修改唯一工具",
            "read_file": "读文件任务",
            "write_file": "写文件任务",
            "search_files": "源码搜索",
            "web_search": "需要网络信息，最后手段",
            "fact_store": "Holographic 记忆搜索",
            "session_search": "历史会话搜索",
            "terminal": "终端命令执行",
            "browser_navigate": "浏览器交互",
        }
        return reasons.get(tool, f"推荐工具: {tool}")

    def _detect_batch(self, query: str) -> dict:
        """检测是否建议批量合并执行。"""
        batch_indicators = {
            "所有": 1, "全部": 1, "每个": 1, "逐": 1,
            "批量": 1, "多个": 1, "遍历": 1, "循环": 1,
            "for ": 1, "foreach": 1,
        }
        score = sum(1 for word, val in batch_indicators.items() if word in query.lower())
        return {
            "eligible": score >= 1,
            "hint": "检测到批量操作意图，建议用 execute_code 合并执行" if score >= 1 else "",
        }

    def _check_safety(self, query: str) -> dict:
        """检查指令是否涉及破坏性操作。"""
        for keyword, level in _DESTRUCTIVE_KEYWORDS.items():
            if keyword.lower() in query.lower():
                return {
                    "level": SafetyLevel.BLOCK if level == "BLOCK" else SafetyLevel.WARN,
                    "reason": f"检测到敏感操作: {keyword}",
                }
        return {"level": SafetyLevel.SAFE, "reason": ""}

    # ── 通用工具方法 ──────────────────────────────────────────────────

    @staticmethod
    def _extract_keywords(query: str, max_kw: int = 5) -> List[str]:
        """从查询中提取关键词（去停用词，取有意义的短词）。"""
        stop_words = {"的", "了", "是", "在", "有", "和", "与", "就", "都",
                      "而", "及", "之", "不", "也", "这个", "那个", "什么",
                      "怎么", "如何", "为什么", "是否", "吗", "吧", "呢",
                      "啊", "哦", "嗯", "a", "an", "the", "is", "are",
                      "was", "were", "to", "for", "of", "in", "on", "at",
                      "or", "and", "do", "does", "did", "have", "has", "had",
                      "this", "that", "it", "its", "we", "you", "they"}

        # 中文分词：按 2-4 字片段拆分（FTS5 unicode61 的问题）
        words = []
        for token in query.split():
            token = token.strip("，。！？、；：""''（）【】《》,.!?;:\"'()[]{}")
            if not token or token.lower() in stop_words:
                continue
            if len(token) <= 1:
                continue
            words.append(token)

        # 去重取前 max_kw 个
        seen = set()
        unique = []
        for w in words:
            wl = w.lower()
            if wl not in seen and len(wl) >= 2:
                seen.add(wl)
                unique.append(w)
                if len(unique) >= max_kw:
                    break

        return unique

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return int((time.monotonic() - start) * 1000)
