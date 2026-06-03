"""信息流管道数据模型 — DIKW 7+1 层检索与工具决策的结构化结果。"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ── 枚举 ──────────────────────────────────────────────────────────────

class SafetyLevel(enum.Enum):
    """安全等级，第7层安全性评估结果。"""
    SAFE = "safe"          # 无风险，可直接执行
    WARN = "warn"          # 需用户确认
    BLOCK = "block"        # 直接阻止，禁止执行


class LayerName(enum.Enum):
    """检索层编号与名称映射。"""
    L0_PRONOUN = 0       # 指代词快速路径
    L1_BRAIN = 1         # 大脑 — 方法论
    L2_LESSON = 2        # 踩坑经验
    L3_KNOWLEDGE = 3     # 知识库
    L4_SESSION = 4       # 近期对话
    L5_CACHE = 5         # 缓存点
    L6_WEB = 6           # 网络搜索
    NO_HIT = -1          # 全部未命中


class TaskCategory(enum.Enum):
    """任务类型分类，用于第7层工具路由。"""
    ANALYSIS = "analysis"           # 数据分析/计算 → execute_code
    FILE_READ = "file_read"         # 读文件 → read_file
    FILE_WRITE = "file_write"       # 写文件 → write_file
    FILE_EDIT = "file_edit"         # 改配置/改代码 → patch
    SEARCH_SRC = "search_source"    # 源码搜索 → search_files
    SEARCH_WEB = "search_web"       # 网络搜索 → web_search
    SEARCH_MEMORY = "search_memory" # 记忆搜索 → fact_store
    SEARCH_SESSION = "search_session"  # 对话搜索 → session_search
    NETWORK = "network"             # 网络请求 → curl/terminal
    SHELL = "shell"                 # 任意终端命令 → terminal
    BROWSER = "browser"             # 浏览器交互 → browser_*
    SKILL = "skill"                 # 匹配到 skill → skill_view + 执行
    UNKNOWN = "unknown"             # 无法分类 → 交给 Agent 判断


# ── 数据类 ────────────────────────────────────────────────────────────

@dataclass
class RetrievalContext:
    """检索上下文，传入 process() 的附加信息。"""
    query: str                              # 用户原始提问
    chat_id: str = ""                       # 会话 ID（可选）
    platform: str = "feishu"                # 通信平台
    prefetched_memory: List[str] = field(default_factory=list)  # 已从 Holographic prefetch 到的内容


@dataclass
class LayerResult:
    """单层检索结果。"""
    hit: bool = False                       # 是否命中
    layer: int = -1                         # 层号
    data: Any = None                        # 命中内容
    source: str = ""                        # 来源描述
    confidence: float = 0.0                 # 可信度
    elapsed_ms: int = 0                     # 本层耗时


@dataclass
class ToolCandidate:
    """第7层推荐的工具候选。"""
    tool_name: str                          # 工具名（如 execute_code / patch / web_search）
    task_category: TaskCategory = TaskCategory.UNKNOWN
    confidence: float = 0.0                 # 匹配度
    reason: str = ""                        # 为什么选这个
    precheck_passed: bool = False           # 可用性验证是否通过
    requires_approval: bool = False         # 是否需要用户确认（P0 底线）


@dataclass
class ToolDecision:
    """第7层工具调用决策输出。"""
    matched_skills: List[str] = field(default_factory=list)       # 触发的 skill 名
    recommendations: List[ToolCandidate] = field(default_factory=list)  # 推荐工具（按优先级）
    safety: SafetyLevel = SafetyLevel.SAFE                        # 安全等级
    safety_reason: str = ""                                       # 安全判断理由
    batch_eligible: bool = False                                  # 是否建议合并执行
    batch_hint: str = ""                                          # 合并建议（如 "3+次同类调用 → execute_code"）
    skill_loaded: bool = False                                    # 是否已加载 skill


@dataclass
class ProcessResult:
    """process() 完整输出：7+1 层检索 + 工具决策。"""
    # ── 第 0-6 层：检索结果 ──
    hit_layer: int = -1                     # 命中层号（-1 = 无命中）
    layer_results: Dict[int, LayerResult] = field(default_factory=dict)  # 每层的详细结果
    consolidated_data: Any = None           # 最终使用的检索数据
    total_elapsed_ms: int = 0               # 检索总耗时

    # ── 第 7 层：工具决策 ──
    tool_decision: ToolDecision = field(default_factory=ToolDecision)

    # ── 执行反馈 ──
    execution_success: Optional[bool] = None    # 执行是否成功（事后填写）
    execution_error: Optional[str] = None       # 执行错误信息
    feedback_stored: bool = False              # 是否已存回方法论
