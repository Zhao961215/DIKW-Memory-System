"""DIKW 信息检索管道 — 稳定接口定义。

所有实现（impl_v1, impl_v2, ...）必须继承此接口。
接口永远不变，变更只影响实现文件。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import ProcessResult, RetrievalContext


class RetrievalPipeline(ABC):
    """DIKW 信息检索管道 — 稳定接口。

    输入用户查询 → 执行 7+1 层检索 + 工具决策 → 返回结构化结果。
    第 0-6 层：逐层检索，命中即返回，不继续下探。
    第 7 层：工具调用决策（5 步全自动）。
    闭环：执行后调 store_feedback() 存回方法论。
    """

    # ── 版本信息 ──────────────────────────────────────────────────────
    VERSION: str = "unknown"          # 实现版本号
    DESCRIPTION: str = ""             # 实现描述

    # ── 核心接口（永远不变） ───────────────────────────────────────────

    @abstractmethod
    async def process(
        self,
        ctx: RetrievalContext,
    ) -> ProcessResult:
        """执行完整 7+1 层：信息检索 → 工具决策。"""
        ...

    @abstractmethod
    async def store_feedback(
        self,
        result: ProcessResult,
        success: bool,
        error_msg: Optional[str] = None,
    ) -> bool:
        """执行后反馈闭环：将结果存回方法论。"""
        ...

    # ── 工厂方法 ──────────────────────────────────────────────────────

    @classmethod
    def create(cls, version: str = "v2") -> "RetrievalPipeline":
        """工厂方法：按版本号创建管道实例。默认 v2（HRR 混合检索）。"""
        if version == "v1":
            from .impl_v1 import ImplV1
            return ImplV1()
        if version == "v2":
            from .impl_v2 import ImplV2
            return ImplV2()
        raise ValueError(
            f"不支持的管道版本: {version!r}。"
            f"可选: {cls.list_versions()}"
        )

    @staticmethod
    def list_versions() -> list[str]:
        """列出所有可用版本。"""
        versions = []
        for ver, mod_name in [("v1", "impl_v1"), ("v2", "impl_v2")]:
            try:
                __import__(f"agent.information_flow.{mod_name}", fromlist=[mod_name])
                versions.append(ver)
            except ImportError:
                pass
        return versions
