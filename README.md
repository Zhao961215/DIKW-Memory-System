# DIKW Memory System for Hermes Agent（Holographic 版）

一个纯 SQLite 的 Agent 记忆系统，基于 [Hermes Agent](https://hermes-agent.nousresearch.com) 内置的 Holographic 插件构建。

**零外部服务、零 Docker、零网络依赖。** 全本地运行，适合中文场景。

---

## 三层架构

| 层 | 是什么 | 定义在哪 |
|----|-------|---------|
| **Agent 层（人格）** | 立场、铁律、思维协议 | `SOUL.md` — 换模型不换人格 |
| **记忆系统层（知识）** | Holographic + v2 检索管道 + 知识库 | `agent/information_flow/` + `docs/` |
| **模型层（天赋）** | 推理能力、算力 | `config.yaml` — 可换模型 |

**核心原则**：模型是天赋，记忆是阅历，SOUL 是人格。

---

## 目录结构

```
├── SOUL.md                    Agent 人格定义（system prompt）
├── AGENTS.md                  工作区目录规范
├── MEMORY.md                  Agent 笔记模板
├── USER.md                    用户画像模板
├── .gitignore
├── LICENSE                     MIT
├── README.md                   本文件
│
├── agent/
│   ├── information_flow/       DIKW 7+1 层检索管道（v2 默认）
│   │   ├── __init__.py         模块入口
│   │   ├── interface.py        稳定接口（永远不改）
│   │   ├── models.py           数据模型
│   │   ├── impl_v1.py          v1 实现（FTS5 仅搜索）
│   │   └── impl_v2.py          v2 实现（HRR 混合 + CJK 分词，默认）
│   ├── skill_auto_trigger.py   技能自动触发（140 行）
│   ├── fact_feedback_loop.py   信任分自动校准（344 行）
│   └── tool_executor_vault_duty.patch  vault-write 强制提炼补丁
│
├── scripts/
│   └── information_flow_health.py  每周健康检查脚本
│
├── skills/
│   ├── dikw-memory-flow.md         DIKW 信息分流
│   ├── memory-capacity-management.md  容量管理
│   └── fact-feedback-loop.md        信任分校准
│
└── docs/
    ├── 记忆系统使用指南.md            完整 SOP
    └── deploy-guide.md               部署教程
```

---

## 核心能力

### DIKW 信息检索管道（7+1 层）

```
指令 → Agent
  ↓
🏃 第 0 层：指代词快速路径 → session_search
  ↓
🧠 第 1 层：大脑 — Holographic（FTS5 + Jaccard + HRR 三重混合）
  ↓ 未命中
📚 第 2-6 层：图书馆（踩坑经验 → 知识库 → 会话 → 缓存 → 网络）
  ↓
🛠️ 第 7 层：工具调用决策（5 步全自动）
  → 执行 → 反馈 → 方法论迭代
```

**v2 相比 v1 的改进**：
- L1：三重混合检索（FTS5 + Jaccard + HRR）取代纯 FTS5
- L1：CJK 2-gram 滑窗分词，解决中文检索不命中问题
- L1：每次命中递增检索计数，修复冷数据统计
- L4：trigram FTS5 中文兜底
- L2-L4：ThreadPoolExecutor 并行执行
- L6：Tavily HTTP 直连（不再占位）

### 四层自愈闭环

```
① 技能自动触发    → 关键词匹配自动注入 skill 内容
② 容量管理        → MEMORY.md > 85% 时自动 DIKW 分流
③ 信任分校准      → 每周统计+自动调优 trust_score
④ vault-write 强制提炼  → 写 vault 文档后自动提醒提炼方法论
```

---

## 快速部署

请对照 `README.md`（部署包内）的 5 步流程：

1. **放四件套**：`cp SOUL.md MEMORY.md USER.md AGENTS.md ~/.hermes/`
2. **填写模板**：按实际内容填充 MEMORY.md（~6000 chars）、USER.md（~3000 chars）
3. **部署模块**：`cp -r agent/information_flow/ ~/.hermes/hermes-agent/agent/`
4. **配置 Holographic**：在 config.yaml 启用 `plugins.hermes-memory-store`
5. **设置健康检查**：创建 cron 每周跑 `scripts/information_flow_health.py`

详见 `docs/deploy-guide.md`。

---

## 版本演进

```
v1 (FTS5 仅搜索)
  → v2 (HRR 混合 + CJK 分词 + 计数 + 并行 + Tavily 直连，当前默认)
    → v3 (欢迎贡献)
```

升级方式：新建 `impl_v3.py` 继承 `RetrievalPipeline`，改 `interface.py` 工厂方法，所有调用方不改一行代码。

---

## License

MIT
