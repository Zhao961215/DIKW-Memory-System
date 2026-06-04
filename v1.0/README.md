# DIKW 记忆系统 v1.0 — 基础版

> **发布时间**：2026-06-01
> **状态**：📦 历史版本（仍可使用，但推荐升级到 [v2.1](../v2.1/)）
> **核心特性**：4-layer 自愈闭环（auto-trigger / 容量管理 / 信任校准 / vault-write 强制提炼）

---

## 一句话定位

**DIKW 记忆系统 v1.0 = Holographic 记忆引擎 + 4-layer 自愈闭环**。这是第一版基础底包，**不包含**信息流 v2 升级和 CIRAAF 5-layer 自愈。

---

## 包含文件

| 文件 | 大小 | 作用 |
|------|------|------|
| `记忆系统使用指南-v1.0.md` | 25 KB | 记忆系统层完整 SOP（含 v1/v2 内部版本变更日志） |
| `README-底包-v1.0.md` | 20 KB | 底包部署说明（SOUL/AGENTS 改名 + 源码补丁） |
| `SOUL.md` | 19 KB | Agent 人格层（铁律、思维协议、DIKW 三问） |
| `AGENTS.md` | 7 KB | 工作区目录规范 |
| `MEMORY.md` | 0.9 KB | 中期记忆 |
| `USER.md` | 0.9 KB | 用户画像 |

---

## 关键特性（4-layer 自愈闭环）

```
① 技能自动触发 → ② 容量管理 → ③ 信任校准 → ④ vault-write 强制提炼
```

| 层级 | 实现 | 频率 |
|------|------|------|
| ① 技能自动触发 | `agent/skill_auto_trigger.py` + `conversation_loop.py` L571 注入 | 每轮对话 |
| ② 容量管理 | `memory-capacity-management` skill + cron 每日 9:00 | 每天 |
| ③ 信任校准 | `agent/fact_feedback_loop.py` + cron 每周六 11:00 | 每周 |
| ④ vault-write 强制提炼 | `agent/tool_executor.py` 源码钩子 | 每次写 vault |

---

## 不包含的内容

- ❌ **信息流 v2 升级**（HRR 混合评分、CJK 2-gram、retrieval_count 修复、Tavily 直连）→ 见 [v2.0](../v2.0/)
- ❌ **CIRAAF 5-layer 自愈**（领域级结构一致性、宏观重构）→ 见 [v2.1](../v2.1/)

---

## 升级路径

从 v1.0 升级到 [v2.1](../v2.1/)（**推荐**）：
1. 直接看 [v2.0/CHANGELOG-from-v1.0.md](../v2.0/CHANGELOG-from-v1.0.md) 了解 v1.0 → v2.0 增量
2. 看 [v2.1/CHANGELOG-from-v2.0.md](../v2.1/CHANGELOG-from-v2.0.md) 了解 v2.0 → v2.1 增量
3. 备份当前 `~/.hermes/` 关键文件（SOUL/AGENTS/MEMORY/USER/memory_store.db）
4. 按 v2.1 的部署步骤操作

---

## 数据来源

- 本版本 = `vault/00-系统文档/记忆系统使用指南.md`（2026-06-02）+ `hermes-holographic-readme-完善版.md`（2026-06-03）
- 仓库历史：https://github.com/Zhao961215/DIKW-Memory-System

---

**最后更新**：2026-06-04
