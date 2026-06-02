---
name: memory-capacity-management
description: MEMORY.md 内存容量管理 — DIKW 分流清理流程。检测占用率 >80% 时自动触发分流（cron 直接执行），占用率 >95% 时即时拦截。
triggers:
  - memory满
  - 记忆满了
  - 记忆满了
  - 整理记忆
  - 记忆管理
  - MEMORY.md
  - 记忆已满
  - 容量管理
  - 清理记忆
  - 记忆存储
tags:
  - memory
  - DIKW
  - system
  - cron
priority: 8
category: system
---

# MEMORY.md 容量管理流程

> **核心原则**：MEMORY.md 是每轮注入的「索引版」，不是「完整版」。
> 满了不是扩容量，是把不属于这里的内容搬走。

## 一、容量检测

每次 `memory` 工具返回 `"error": "...would exceed the limit"` 或占用率 >80%
→ 触发本流程。

### 检测阈值

| 等级 | 占用率 | 动作 |
|------|--------|------|
| 🟢 正常 | <70% | 无需处理 |
| 🟡 注意 | 70-85% | 推送一句话提醒："MEMORY.md 占用率 X%，建议近期整理" |
| 🟠 告警 | >85% | **自动执行 DIKW 分流**：调 memory 读取全部条目 → 逐条三问判断 → fact_store/write_file 分流 → memory replace 替换索引行 → 验证占用率 → 推送清理报告 |
| 🔴 满仓 | >95% | 同上（自动分流），但即时拦截新写入 |

## 二、DIKW 逐条分流流程

### Step 1：读取全部条目

`memory(action='list' 或查看注入 context)`

### Step 2：逐条跑三问

```
[当前条目] → 三问判断 → 判定层 → 目标位置 → 执行
```

| 三问 | 答案 | 判定层 | 目标 |
|------|------|--------|------|
| 会变吗？ | ❌ 不变 | W / K | Holographic 或 vault |
| 会变吗？ | ✅ 会变 | I / D | data cache（带时间戳） |
| 每次推理要用？ | ✅ 高频 | W | Holographic（fact_store） |
| 每次推理要用？ | ❌ 偶尔 | K | vault（read_file） |
| 卡片还是书？ | 卡片 | K 实体 | entities/ 实体页 |
| 卡片还是书？ | 体系化 | K 文档 | vault/ 分类目录 |

### Step 3：执行分流

#### W 层 → Holographic 大脑
```json
fact_store(
  content="方法论一句话", 
  query="同义词 关键词 覆盖 广谱", 
  source="from_memory_capacity_management"
)
```

#### K 层详细文档 → vault
```
write_file → ~/.hermes/data/knowledge/vault/06-系统运维/文档名.md
```

#### K 层实体卡片 → entities
```
write_file → ~/.hermes/data/knowledge/vault/entities/对应分类/名.md
```

#### I 层动态数据 → data cache
```
write_file → data/investment/对应模块/cache/文件名.md（带时间戳）
```

### Step 4：替换为索引行

替换后格式（一行，包含详见路径）：

```
- [分类-关键词] | 一句话说明 + 详见 vault/entities/skill
```

**示例对比**：

| 原始（~600字） | 替换后（~120字） |
|---------------|----------------|
| Temperature 机制完整诊断代码 | `[系统-temperature机制] | MiniMax temperature 已从代码删除，详见 vault/06-系统运维/hermes-temperature-mechanism.md` |
| Hindsight 误诊完整验证 | `[系统-hindsight误诊纠错] | hindsight API 路径 bug 系误诊，详见 vault/06-系统运维/hindsight-misdiagnosis-20260602.md` |

### Step 5：确认方法论已存 Holographic

替换后自检：
- 这条信息里有**方法论/原则**吗？（如"修源码前必须验证"）
- → 有则 `fact_store` 存一份到大脑
- → 无则跳过

## 三、分类指南速查

| 条目类型 | 特征词 | 判定 | 目标 |
|---------|--------|------|------|
| 诊断/排查记录 | "验证发现/根因是/原因是/通过 XX 确认" | **K 层文档** | vault/06-系统运维/ |
| 踩坑教训 | "踩坑/主上纠正/铁律" | **W 层方法论** + K 层文档 | fact_store + vault |
| 调仓/决策 | "方案 A/减 XX/加 XX" | **I 层动态数据** | data/investment/decisions/ |
| 基金/行业信息 | "XXX 基金/XXX 行业 PE /特征" | **K 层实体卡片** | vault/entities/funds/ 或 industry/ |
| 配置说明 | "环境变量/端口/config.yaml" | **K 层文档** | vault/06-系统运维/ |

## 四、验证步骤

分流后自检：
- [ ] 每条被移除的详细内容都已写入目标位置（vault / entities / Holographic / cache）
- [ ] MEMORY.md 中保留了可检索的索引行
- [ ] 方法论/原则已通过 `fact_store` 存到 Holographic
- [ ] 总占用已降至 <60%
- [ ] 向用户报告清理结果

## 五、Cron 联动

本 skill 配套 cron 任务 `check-memory-capacity`（job_id: `14219901e564`），每周五 10:00 自动检查并执行。

| 等级 | 占用率 | 动作 |
|------|--------|------|
| 🟢 正常 | <70% | 静默，不打扰 |
| 🟡 注意 | 70-85% | 推送一句话提醒："MEMORY.md 占用率 X%，建议近期整理" |
| 🟠 告警 | >85% | **自动执行 DIKW 分流**：调 memory 读取全部条目 → 逐条三问判断 → fact_store/write_file 分流 → memory replace 替换索引行 → 验证占用率 → 推送清理报告 |

Cron agent 会话自动加载本 skill 作为方法论指导，有完整工具链（memory / fact_store / write_file / patch）。

## 相关 skill

- `memory-daily-organizer` — 每日 session 知识提取（互补，本 skill 专注容量管理）
- `dikw-memory-flow` — DIKW 分流基础流程（三问判断表、存储位置速查）

## 变更日志

- 2026-06-02: v2 — cron 行为改为 >85% 自动分流（非提醒）。新增 reference 部署文档。
