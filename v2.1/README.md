# DIKW 记忆系统 v2.1 — CIRAAF 5-layer 自愈（最新稳定版）⭐

> **发布时间**：2026-06-03
> **状态**：✅ **当前推荐版本**
> **核心特性**：5-layer 自愈闭环（含 **CIRAAF 领域级结构一致性** 宏观重构）

---

## 一句话定位

**v2.1 = v2.0 全部内容 + CIRAAF 5-layer 自愈**。在 v2.0 的 4-layer 基础上，新增第⑤层 CIRAAF 宏观重构，处理**领域级**结构一致性问题。

---

## 包含文件

| 文件 | 大小 | 作用 |
|------|------|------|
| `记忆系统使用指南-完善版-v2.1.md` | 49 KB | 记忆系统层完整 SOP（v2.0 + v2.1 增量） |
| `CIRAAF-源码部署指导-v2.1.md` | 29 KB | **CIRAAF 三齿轮架构 + 完整源码 + 部署步骤** |
| `SOUL.md` | 19 KB | Agent 人格层 |
| `AGENTS.md` | 7 KB | 工作区目录规范 |
| `MEMORY.md` | 0.9 KB | 中期记忆 |
| `USER.md` | 0.9 KB | 用户画像 |
| `CHANGELOG-from-v2.0.md` | — | v2.0 → v2.1 增量对比 |

---

## 🆕 相对 v2.0 的关键升级（CIRAAF 5-layer 自愈）

### 5-layer 自愈闭环

```
① 技能自动触发 → ② 容量管理 → ③ 信任校准 → ④ vault-write 强制提炼 → ⑤ CIRAAF 宏观重构
```

**第⑤层 CIRAAF（新增）**：

| 维度 | 说明 |
|------|------|
| 定位 | 领域级结构一致性 |
| 实现 | `agent/cirAAF_mechanic.py` + `brain-periodic-refactor` skill + cron 每周日 10:00 |
| 三齿轮 | Gear 1（源码机械引擎）+ Gear 2（cron skill 反射）+ Gear 3（源码应用修复） |
| 5 大领域 | 投资 63 / 系统 62 / 用户 64 / 开发 60 / 方法 57（健康分） |
| 机械衰减 | DB >60 天激活；年龄守卫保护幼年数据 |
| 零 LLM 比例 | 3 个 cron 中 2 个是 no_agent（~66% 零 LLM） |

### 跨版本对比

| 层级 | v1.0 | v2.0 | **v2.1** |
|------|------|------|----------|
| ① 技能自动触发 | ✅ | ✅ | ✅ |
| ② 容量管理 | ✅ | ✅ | ✅ |
| ③ 信任校准 | ✅ | ✅ | ✅ |
| ④ vault-write 强制提炼 | ✅ | ✅ | ✅ |
| **⑤ CIRAAF 宏观重构** | ❌ | ❌ | ✅ **新增** |

---

## ✅ 保留 v2.0 的内容

- 4-layer 自愈闭环
- 信息流 v2 升级（HRR 混合 + CJK 2-gram + retrieval_count 修复 + Tavily 直连）
- DIKW 三层分流
- 6 层递进检索流水线

---

## 部署 CIRAAF 增量

```bash
# 1. 复制 CIRAAF 机械引擎
cp agent/cirAAF_mechanic.py ~/.hermes/hermes-agent/agent/

# 2. 创建 cron 包装脚本
cp scripts/cirAAF_mechanic.sh ~/.hermes/scripts/

# 3. 注册 cron（每周日 10:00，no_agent 模式）
cronjob(action='create', name='cirAAF-mechanic',
        script='cirAAF_mechanic.sh',
        schedule='0 10 * * 0',
        no_agent=True)

# 4. 健康验证
python3 -m agent.cirAAF_mechanic --report
```

---

## 数据来源

- 本版本 = 49K 完善版指南 + `vault/00-系统文档/CIRAAF-源码部署指导.md`（2026-06-03 02:39）
- 源码层：`agent/cirAAF_mechanic.py`

---

**最后更新**：2026-06-04
