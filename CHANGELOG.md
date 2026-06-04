# CHANGELOG — DIKW 记忆系统跨版本演进

> **项目**：DIKW-Memory-System
> **仓库**：https://github.com/Zhao961215/DIKW-Memory-System
> **当前推荐版本**：**v2.1**（含 5-layer 自愈 + CIRAAF）

---

## 版本对比总览

| 维度 | v1.0 | v2.0 | **v2.1（最新）** |
|------|------|------|------------------|
| **发布时间** | 2026-06-01 | 2026-06-03 | 2026-06-03 |
| **状态** | 📦 历史版本 | 📦 历史版本 | ✅ **推荐** |
| **自愈层数** | 4-layer | 4-layer | **5-layer** |
| **信息流版本** | v1 | v2（HRR+CJK 2-gram+retrieval_count修复+Tavily）| v2 |
| **CIRAAF 5-layer** | ❌ | ❌ | ✅ |
| **仓库 description** | 4-layer | 4-layer | **5-layer + CIRAAF** |
| **README 文档** | 20K | — | 20K（描述已更新）|
| **完整指南** | 25K | 49K | 49K + 30K CIRAAF |
| **领域划分** | 4-layer 硬编码 | 4-layer 硬编码 | 5 大领域硬编码（投资/系统/用户/开发/方法） |

---

## v2.2 (2026-06-04) — 零配置自动聚类 ⚠️ 破坏性升级

**核心升级**：把硬编码 5 大领域改为**自动聚类**——按 Holographic 实际 fact 数据自动发现 N 个"自然领域"。

**为什么**：v2.1 硬编码 5 大领域是**主上本地专用**（投资/系统/用户/开发/方法），别人下载后领域是空的（或数字是错的）。v2.2 改成"按 Holographic 实际数据自动聚类"——**别人下载立即贴合自己**，零配置。

**改动清单**：
| 类别 | 改动 |
|---|---|
| 新增 | `auto_discover_domains()` 函数（~150 行）—— Jaccard 贪心连通子图聚类 + Top 3 关键词命名 |
| 新增 | `load_or_discover_domains()` 函数——带缓存（`~/.hermes/data/cirAAF/domain_cache.json`） |
| 新增 | `--rediscover` 命令行参数——强制重发现，忽略缓存 |
| 删除 | 硬编码 `DOMAINS` 字典（37 行）|
| 改造 | `scan_domain()` / `_check_domain_decay_readiness()` / `apply_decay()` / `build_refactor_package()` —— 从 `category IN (cats)` 改为 `fact_id IN (members)` |
| 改造 | `main()` —— 先 `load_or_discover_domains()` 再扫描所有领域 |
| 新增 | `HOLOGRAPHIC_DB_PATH` / `HOLOGRAPHIC_REPORT_DIR` 环境变量——支持隔离部署 + mock 测试 |

**算法**（4 步）：
1. 拉所有 `trust > 0.3` 的 fact（排除已降权垃圾）
2. 提取特征（中文 2-gram + 英文单词 + tags + category）
3. 倒排索引 + Jaccard 贪心聚类（O(n × 200) ≈ 1.5M 次/7774 facts）
4. Top 3 关键词命名（如"投资-PE+动量+止盈"）

**零 LLM 比例**：从 ~66% 升到 **~95%**（聚类 + 健康分全零 LLM，只有 v2.3+ 的 LLM 命名才需要 LLM）。

**⚠️ 破坏性变更**：
- 旧 `python3 -m agent.cirAAF_mechanic --domain 投资` 命令**失效**（领域名变了）
- 解决：先用默认报告看真实领域名（聚类关键词拼接）
- 旧 `~/.hermes/data/cirAAF/health_history.json` 兼容（领域键变 → 历史记录从 0 开始）

**升级方法**：标准 3 步（拉新版 + 跑一次 + 看输出）

```bash
# 1. 拉新版（标准升级流程）
git pull origin main

# 2. 跑一次（自动聚类，结果写缓存）
python3 -m agent.cirAAF_mechanic

# 3. 看输出（领域名是动态生成的"关键词+关键词+关键词"格式）
# 如：投资-PE+动量+止盈  (健康分: 56/100)
```

**缓存机制**：
- 首次跑：自动聚类（~30 秒/7774 facts）+ 写缓存
- 后续跑：读缓存（瞬时）—— 除非 fact 总数增长 20% 才重发现
- 强制重发现：`--rediscover` 或 `load_or_discover_domains(force_rediscover=True)`

**已知限制**：
- 聚类名每次可能微变（top 关键词变化）—— 旧 --domain 命令可能失效 → 解决：定期用默认报告看新聚类名
- 中文 stop word 词典 27 个——可能漏掉一些（比如"也"在"也是"是 stop 但在"也买"是关键词）—— v2.3+ 优化

---


### v2.2.1 (2026-06-04) — 零配置算法修复（v2.2 必备补丁）

发布后实测发现 3 个算法 bug + 1 个数据丢失 bug，全部修复：

- **STOP_TAGS 黑名单**：Hindsight 时代残留元数据 tag（`auto-retain`/`observation`/`discovery` 等 12 个）污染聚类结果 → 过滤
- **IDF 过滤**：通用 2-gram（"使用"/"一个"等）成 hub 节点拉了 22% fact 成一类 → IDF_THRESHOLD=0.30
- **健康分公式**：v2.2 公式 `int(avg × (1-zero_ret) × 100)` 在 zero_ret=100% 时直接归零 → 改回 v2.1 风格 + 软惩罚
- **单点 fact 丢失 bug**（**严重**）：贪心聚类的 `else: visited.add(fid)` 让单点也 visited，misc 收容逻辑收不到 → 7254 条 fact 丢失，删 else 分支修复
- **MIN_CLUSTER_SIZE=25**：v2.2 默认 5，22% 巨聚类 + 13 个 <30 条小聚类，v2.1 5 大领域感更友好

**v2.2 升 v2.2.1 步骤**：
```bash
git pull origin main
python3 -m agent.cirAAF_mechanic --rediscover
```

## v2.1 (2026-06-03) — 5-layer + CIRAAF ⭐ 当前

**核心升级**：
- 新增第⑤层 CIRAAF 宏观重构（领域级结构一致性）
- 仓库 description 更新为 5-layer + CIRAAF
- 三齿轮架构：Gear 1（源码机械引擎）+ Gear 2（cron skill 反射）+ Gear 3（源码应用修复）
- 5 大领域健康监控：投资 63 / 系统 62 / 用户 64 / 开发 60 / 方法 57
- 零 LLM 比例：66%（4/6 cron no_agent）

**部署**：
```bash
# 完整 v2.1 部署
cp -r v2.1/* ~/.hermes/
cp agent/cirAAF_mechanic.py ~/.hermes/hermes-agent/agent/
hermes restart
```

详见：[v2.1/CHANGELOG-from-v2.0.md](v2.1/CHANGELOG-from-v2.0.md)

---

## v2.0 (2026-06-03) — 信息流 v2 升级

**核心升级**：
- 信息流 v2 升级：`agent/information_flow/impl_v2.py` 成为默认
  - L1 FTS5 + Jaccard + HRR 三重混合评分
  - CJK 2-gram 滑窗分词（修复 unicode61 不分割 CJK）
  - retrieval_count 字段递增（修复 99.8% 冷数据假象）
  - L2-L4 ThreadPoolExecutor 并行
  - L6 Tavily HTTP 直连
- 49K 完善版指南替换 25K 早期版

**数据**：
- 中文长句检索：0% 命中 → 100% 命中（6/6 测试）
- 冷数据比：99.8% 假象 → 真实统计
- L2-L4 串行耗时：7T → T（并行）

详见：[v2.0/CHANGELOG-from-v1.0.md](v2.0/CHANGELOG-from-v1.0.md)

---

## v1.0 (2026-06-01) — 4-layer 基础版

**核心特性**：
- Holographic 记忆引擎（SQLite + FTS5 + HRR 双引擎）
- 4-layer 自愈闭环：
  - ① 技能自动触发（`agent/skill_auto_trigger.py`）
  - ② 容量管理（`memory-capacity-management` skill + cron 每日 9:00）
  - ③ 信任校准（`agent/fact_feedback_loop.py` + cron 每周六 11:00）
  - ④ vault-write 强制提炼（`agent/tool_executor.py` 源码钩子）
- DIKW 三层分流（D / I / K / W）
- 6 层递进检索流水线

详见：[v1.0/README.md](v1.0/README.md)

---

## 选择建议

| 你的情况 | 推荐版本 |
|---------|---------|
| 全新部署 / 想用最新功能 | **v2.1** |
| 已有 v1.0 部署，想升级 | 直接升级到 **v2.1**（增量包含 v2.0）|
| 已有 v2.0 部署，想升级到 v2.1 | [v2.1/CHANGELOG-from-v2.0.md](v2.1/CHANGELOG-from-v2.0.md) |
| 维护中，不想升级 | 保留当前版本，但关注 [Releases](https://github.com/Zhao961215/DIKW-Memory-System/releases) |
