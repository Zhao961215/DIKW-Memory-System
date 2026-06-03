"""DIKW 信息检索管道 — 模块入口。

模块内接口稳定（interface.py），实现可更换（impl_v1.py / impl_v2.py / ...）。
当 Hermes 新版本发布时，只需：
  1. 新增 impl_v2.py（继承 RetrievalPipeline）
  2. 更新 interface.py 的 create() 工厂方法
  3. 所有调用方不改一行代码
"""

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

__all__ = [
    "RetrievalPipeline",
    "RetrievalContext",
    "ProcessResult",
    "LayerResult",
    "LayerName",
    "ToolDecision",
    "ToolCandidate",
    "TaskCategory",
    "SafetyLevel",
]
