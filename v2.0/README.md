# DIKW 记忆系统 v2.0 — 信息流 v2 升级版

> **发布时间**：2026-06-03
> **状态**：📦 历史版本（推荐升级到 [v2.1](../v2.1/)，该版本包含 CIRAAF 5-layer）
> **核心特性**：4-layer 自愈闭环 + **信息流 v2 升级**（HRR 混合 + CJK 2-gram + retrieval_count 修复 + Tavily 直连）

---

## 一句话定位

**v2.0 = v1.0 全部内容 + 信息流 v2 升级**。代码层升级到 `agent/information_flow/impl_v2.py`，文档层升级到「49K 完善版」指南。

---

## 包含文件

| 文件 | 大小 | 作用 |
|------|------|------|
| `记忆系统使用指南-完善版-v2.0.md` | 49 KB | 记忆系统层完整 SOP（含信息流 v2 升级内容） |
| `SOUL.md` | 19 KB | Agent 人格层 |
| `AGENTS.md` | 7 KB | 工作区目录规范 |
| `MEMORY.md` | 0.9 KB | 中期记忆 |
| `USER.md` | 0.9 KB | 用户画像 |
| `CHANGELOG-from-v1.0.md` | — | v1.0 → v2.0 增量对比 |

---

## 🆕 相对 v1.0 的关键升级（信息流 v2）

### L1 大脑：FTS5 + Jaccard + HRR 三重混合评分
- v1.0：仅 FTS5
- **v2.0**：FTS5（0.4 权重）+ Jaccard（0.3 权重）+ HRR（0.3 权重，可调）

### CJK 2-gram 滑窗分词
- v1.0：FTS5 unicode61 不分割连续汉字，"左侧建仓策略" 当作单 token
- **v2.0**：对 >4 字的 CJK token 拆 2-gram，"左侧建仓策略" → ["左侧","侧建","建仓","仓策","策略"]

### retrieval_count 字段修复
- v1.0：SELECT 不 UPDATE `retrieval_count` → 99.8% 冷数据假象
- **v2.0**：每次 L1 命中后 `UPDATE facts SET retrieval_count = retrieval_count + 1`

### L2-L4 并行执行
- v1.0：串行逐层
- **v2.0**：ThreadPoolExecutor 并行（踩坑经验 / 知识库 / 近期对话）

### L6 网络搜索：Tavily 直连
- v1.0：占位（返回未命中）
- **v2.0**：Tavily HTTP API 直连（web_search 后端）

### L4 近期对话：trigram 中文兜底
- v1.0：FTS5 不命中即返回空
- **v2.0**：trigram FTS5 中文兜底

---

## ✅ 保留 v1.0 的内容

- 4-layer 自愈闭环（auto-trigger / 容量管理 / 信任校准 / vault-write）
- DIKW 三层分流（D / I / K / W）
- 6 层递进检索流水线
- FTS5 中文分词修复（基础补丁 + 进阶加固）
- HRR 关键词编码策略
- SOUL 铁律 + 思维协议

---

## ❌ 不包含的内容

- ❌ **CIRAAF 5-layer 自愈**（领域级结构一致性、宏观重构）→ 见 [v2.1](../v2.1/)

---

## 升级路径

从 v1.0 升级到 v2.0：
1. 备份 `~/.hermes/hermes-agent/agent/information_flow/` 目录
2. 复制 v2.0 的 `agent/information_flow/impl_v2.py` 到 `~/.hermes/hermes-agent/agent/information_flow/`
3. 重启 Gateway
4. 验证：用 `fact_store(query="测试中文检索")` 应能命中（之前返回空）

从 v2.0 升级到 [v2.1](../v2.1/)（**推荐**）：
1. 看 [v2.1/CHANGELOG-from-v2.0.md](../v2.1/CHANGELOG-from-v2.0.md)
2. 部署 CIRAAF：`cp agent/cirAAF_mechanic.py ~/.hermes/hermes-agent/agent/`
3. 注册 cron 每周日 10:00

---

## 数据来源

- 本版本 = `vault/00-系统文档/hermes-holographic-记忆系统指南-完善版.md`（2026-06-03 22:38）
- 源码层：`agent/information_flow/impl_v2.py`（默认版本）

---

**最后更新**：2026-06-04
