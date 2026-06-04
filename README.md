# DIKW-Memory-System

> **Pure SQLite memory system for Hermes Agent. Zero Docker, zero external services. 5-layer self-healing (v2.1+) + CIRAAF. 中文 FTS5 patches included.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Zhao961215/DIKW-Memory-System)](https://github.com/Zhao961215/DIKW-Memory-System/stargazers)
[![Forks](https://img.shields.io/github/forks/Zhao961215/DIKW-Memory-System)](https://github.com/Zhao961215/DIKW-Memory-System/network)

---

## 🎯 解决什么问题？

**痛点**：传统 AI Agent 记忆系统的三个致命问题：
- 🧠 **检索漂移** — 中文长句检索命中率 0%（unicode61 不分割 CJK）
- 🗑️ **记忆腐烂** — 1000+ 条 fact，过期方法论/重复定义永远不会被清理
- 🔀 **结构混乱** — 同一概念 5 个版本并存，跨领域规则不一致

**方案**：DIKW 4 层分流 + 5-layer 自愈闭环
- ① 技能自动触发 · ② 容量管理 · ③ 信任校准 · ④ vault-write 强制提炼 · ⑤ **CIRAAF 宏观重构**
- **66% 任务零 LLM 调用** · **自动聚类领域实时健康监控**（v2.2+ 零配置）

**用 v2.1 的效果**：记忆系统每周日自动"自我体检 + 自我修复"，无需人工干预。

---
## 🚀 选版本（必读）

| 版本 | 发布时间 | 状态 | 自愈层 | 适用场景 |
|------|---------|------|--------|---------|
| **[v2.1](v2.1/)** ⭐ | 2026-06-03 | ✅ 推荐 | **5-layer + CIRAAF** | 全新部署 / 升级到最新 |
| [v2.0](v2.0/) | 2026-06-03 | 📦 历史 | 4-layer + 信息流 v2 | 升级中间态 |
| [v1.0](v1.0/) | 2026-06-01 | 📦 历史 | 4-layer 基础 | 学习/研究/老环境 |

**👉 全新用户：直接看 [v2.1/README.md](v2.1/README.md)**

**👉 升级用户：先看 [CHANGELOG.md](CHANGELOG.md) 选对应升级路径**

---

## 📦 项目简介

DIKW-Memory-System 是 Hermes Agent 的完整记忆系统底包，基于 Holographic 记忆引擎实现：

- 🧠 **Holographic 大脑**：SQLite + FTS5 + HRR 双引擎，零外部依赖
- 📚 **Vault 图书馆**：体系化文档、完整报告、知识库
- 🗂️ **Entities 卡片柜**：结构化实体卡片
- 📦 **Data Cache 数据缓存**：动态数据带时间戳
- 🔄 **5-layer 自愈闭环**（v2.1+）：技能触发 → 容量管理 → 信任校准 → vault-write 强制提炼 → **CIRAAF 领域级重构**

**核心理论**：DIKW（Data→Information→Knowledge→Wisdom）信息分流框架，让 AI Agent 的"记忆"从"随机能力"变成"可复现能力"。

---

## 🎯 5-layer 自愈闭环（v2.1+）

```
┌─────────────────────────────────────────────────────────┐
│                    5-layer 自愈闭环                        │
├─────────────────────────────────────────────────────────┤
│ ① 技能自动触发  agent/skill_auto_trigger.py              │
│    └─ 每轮对话匹配 triggers 关键词，自动注入 skill         │
│ ② 容量管理      memory-capacity-management skill         │
│    └─ cron 每日 9:00，>85% 自动 DIKW 分流                │
│ ③ 信任校准      agent/fact_feedback_loop.py              │
│    └─ cron 每周六 11:00，三规则自动校准                   │
│ ④ vault-write  agent/tool_executor.py（源码钩子）         │
│    └─ 写 vault/ 后 100% 注入 [DUTY] 提醒                 │
│ ⑤ CIRAAF 宏观重构 agent/cirAAF_mechanic.py              │
│    └─ cron 每周日 10:00，领域级结构一致性                 │
└─────────────────────────────────────────────────────────┘
```

**零 LLM 比例：66%**（4/6 cron 任务 no_agent 模式，绕过 Agent 推理层）

---

## 🚀 快速开始（推荐 v2.1）

```bash
# 1. 下载 v2.1 底包
curl -L https://github.com/Zhao961215/DIKW-Memory-System/archive/refs/tags/v2.1.tar.gz -o dikw-v2.1.tar.gz
tar -xzf dikw-v2.1.tar.gz
cd DIKW-Memory-System-2.1/v2.1/

# 2. 部署配置（按 README-底包 步骤改名 + 复制）
# 详见 v2.1/README.md

# 3. 部署 CIRAAF（v2.1 增量）
cp agent/cirAAF_mechanic.py ~/.hermes/hermes-agent/agent/
cp scripts/cirAAF_mechanic.sh ~/.hermes/scripts/cirAAF_mechanic.sh
chmod +x ~/.hermes/scripts/cirAAF_mechanic.sh
cp scripts/information_flow_health.py ~/.hermes/scripts/
mkdir -p ~/.hermes/skills/system
cp -r skills/system/brain-periodic-refactor ~/.hermes/skills/system/
hermes restart

# 4. 注册 CIRAAF 周健康报告 cron（每周日 10:00，no_agent 模式）
# ⚠️ 必须设 workdir + script 绝对路径，否则裸名解析失败（CIRAAF 周报从未跑过的根因）
hermes cron add --name "CIRAAF 周健康报告" \
    --schedule "0 10 * * 0" \
    --no-agent \
    --workdir "/home/$USER/.hermes/hermes-agent" \
    --script "/home/$USER/.hermes/scripts/cirAAF_mechanic.sh" \
    --deliver origin

# 5. 健康检查（默认输出健康报告；--decay 三条件检查）
python3 -m agent.cirAAF_mechanic
python3 ~/.hermes/scripts/information_flow_health.py
```

---

## 📚 文档结构

```
DIKW-Memory-System/
├── README.md              # 本文件（项目入口）
├── CHANGELOG.md           # 跨版本演进对比
├── LICENSE                # MIT
├── v1.0/                  # 4-layer 基础版
│   ├── README.md
│   ├── 记忆系统使用指南-v1.0.md
│   ├── SOUL.md / AGENTS.md / MEMORY.md / USER.md
│   └── README-底包-v1.0.md
├── v2.0/                  # 4-layer + 信息流 v2
│   ├── README.md
│   ├── 记忆系统使用指南-完善版-v2.0.md
│   ├── SOUL.md / AGENTS.md / MEMORY.md / USER.md
│   └── CHANGELOG-from-v1.0.md
├── v2.1/                  # 5-layer + CIRAAF ⭐
│   ├── README.md
│   ├── 记忆系统使用指南-完善版-v2.1.md
│   ├── CIRAAF-源码部署指导-v2.1.md
│   ├── SOUL.md / AGENTS.md / MEMORY.md / USER.md
│   └── CHANGELOG-from-v2.0.md
└── docs/
    └── 部署指南.md
```

---

## 📥 Releases（可下载版本）

每个版本都附 3 个文件：
- `DIKW-记忆系统-vX.X-框架.docx` — 本地存档用
- `DIKW-记忆系统-vX.X-完整版.md` — 在线查看
- `DIKW-记忆系统-vX.X-底包.zip` — 部署用

前往 [Releases 页面](https://github.com/Zhao961215/DIKW-Memory-System/releases) 下载。

---

## 🤝 贡献 / 反馈

- 提 Issue：https://github.com/Zhao961215/DIKW-Memory-System/issues
- 维护者：Zhao961215
- 协议：MIT

---

## 📜 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。
