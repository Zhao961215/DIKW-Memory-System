---
name: dikw-memory-flow
description: DIKW 信息分流流程 — 记住/保存/记录/存一下/归档/复盘类指令必须先走三问再分流。分析完成后自动自检是否需要持久化。
triggers: [记住, 保存, 记录, 存一下, 归档, 归纳, 分流, 记忆, 梳理一下, 整理一下, 复盘]
tags: [memory, DIKW, workflow]
priority: 10
category: system
---

# DIKW 信息分流流程（自检模式）

> **概念速查 → `~/.hermes/data/knowledge/vault/00-系统文档/记忆系统使用指南.md`**（大脑 vs 图书馆、DIKW 模型、检索规则、时效管理一页讲清）
> 本 skill 是**操作指南**，专注分流实操步骤。
> 💡 触发方式：**系统自动绑定**（v2026.5.29.2+）。Agent 无需手动扫描——`agent/skill_auto_trigger.py` 模块在每一轮用户消息构建前自动匹配 frontmatter `triggers` 字段，命中时将该 skill 内容注入到 user_message 前。`triggers` 现在是系统的自动触发机制，需妥善维护关键词。
>
> ⚠️ 若未命中自动触发（如 SKILL.md 无 `triggers` 字段或被排除），回退到手动加载：扫描 `<available_skills>` 列表 → `skill_view(name)`。
>
> 详见 fact #7918 与 `agent/skill_auto_trigger.py`

## 三层架构定位

本 skill 定义**记忆系统层**的操作流程。完整 Agent 由三层构成：

| 层 | 是什么 | 定义在哪 |
|----|-------|---------|
| 模型层（天赋/能量） | 推理能力、算力、创造力 | config.yaml |
| 记忆系统层（知识/经验） | Holographic + Vault + Entities + Cache | **本 skill + 记忆系统使用指南.md** |
| Agent 层（人格/规则） | 立场、铁律、思维协议 | SOUL.md |

> 模型是天赋，记忆是阅历，SOUL 是人格。三者共同定义 Agent。
> DIKW 完整指南 → `~/.hermes/data/knowledge/vault/00-系统文档/记忆系统使用指南.md`
> Agent 行为规则 → SOUL.md § 信息检索流水线

## 核心原则：访问频率决定存储位置

**Holographic（大脑）存的是高频调用的不变内容**，不是索引标签。

```
访问频率高（每次推理都用）  → Holographic（大脑）
访问频率低（偶尔查一次）    → 知识库 / 实体页
会变化的数据（有保质期）    → data cache（带时间戳）
```

## 分流流程（校正版）

```
信息产生
  ↓
[Step 1] 判断信息类型
  │
  ├── D (Data) → 原始数字、未处理缓存
  │   → data cache 目录（~/.hermes/data/investment/ 下各模块子目录）
  │   → 默认有效期 30 天
  │
  ├── I (Information) → 会变化的动态数据
  │   → 净值、动量、PE 分位、价格位置、短期判断
  │   → 存入 data cache（带时间戳），不在 hindsight 驻留
  │   → 读取时核实时效性：净值1天、动量7天、PE分位7天、持仓30天
  │
  ├── K (Knowledge) → 结构化卡片
  │   → 基金信息、行业定义、概念解释、决策记录
  │   → 存 ~/.hermes/data/knowledge/vault/entities/（funds/、industry/ 等）
  │
  └── W (Wisdom) → 不变的方法论、框架、原则
      → 完整版：知识库（~/.hermes/data/knowledge/vault/02-投资研究/）
      → 索引摘要：Holographic（大脑，高频检索用）
      → 示例：基金红线、操作原则、投资框架、分析方法论

[Step 2] 检查是否已有同类信息
  → 有 → 更新/覆盖，不重复创建
  → 无 → 新建

[Step 3] 执行存储
  → data cache：write_file 到对应模块的 data/ 目录\n  → 大脑（Holographic）：`fact_store`（方法论文档的索引摘要）\n  → entities：write_file 到 ~/.hermes/data/knowledge/vault/entities/ 对应子目录\n  → 知识库：write_file 到 ~/.hermes/data/knowledge/vault/ 对应分类目录

[Step 4] 告知用户
  → 一句话说明存到哪里 + 为什么存那里
```

## 判断标准表（校正版）

| 信息类型 | 特征 | 存储位置 | 说明 |
|---------|------|---------|------|
| **原始数据** | 未处理缓存、API返回原始JSON | `data/investment/<模块>/cache/` | 30天自动清理 |
| **动态数据** | 净值、动量分、PE分位、价格位置 | `data/investment/<模块>/cache/` + 带时间戳 | 读取时核实时效性 |
| **短期判断** | "有色金属当前33%低估，动量偏弱" | `data/investment/<模块>/cache/`（带时间戳） | 过期后重新获取 |
├── 基金/行业卡片 | 基金基本信息、持仓、费率、行业PE规律 | `~/.hermes/data/knowledge/vault/entities/funds/` / `~/.hermes/data/knowledge/vault/entities/industry/` | 更新时覆盖 |
|| **投资原则/红线** | "市场高估时不建仓"、"仓位管理公式" | **Holographic**（大脑，高频调用） | 每次推理直接可用 |
|| **方法论/框架** | 探风三层确认逻辑、时值评分框架 | Holographic(摘要) + 知识库(完整版) | 摘要快速检索，完整版深度查阅 |
|| **操作策略** | "004433目标买入价1.68，双条件触发" | 知识库(完整分析) + Holographic(索引) | 完整报告存知识库，关键数字存大脑 |
|| **部署/配置文档** | 技术操作手册、安装步骤 | 知识库（`~/.hermes/data/knowledge/vault/06-系统运维/`） | 低频查阅 |
|
|**✨ 写完必提规则（2026-06-02 源码级强制）**| 写入 vault 完整文档后 → **自动提炼 1-3 条核心方法论 → fact_store（大脑）** | 确保 K→W 链条不断 | `tool_executor.py` `_inject_vault_duty()` 源码钩子自动在 tool result 尾部注入 [DUTY] 提醒 |

## 已有缓存点速查

以下目录天然是 DIKW 的 Data/Information 缓存层，不需要另建：

| 目录 | 用途 | 管理方式 |
|------|------|---------|
| `~/.hermes/data/investment/wab/cache/` | 挖呗扫描 + 探风动量（PE分位、sw_momentum等，两者共享 wab/cache/） | 脚本自动覆盖 |
| `~/.hermes/data/investment/scores/` | 时值模型评分数据 | 脚本自动覆盖 |
| `~/.hermes/data/investment/cache/` | 基金净值/持仓缓存、股票财务、nav 历史净值等 | 定时清理 |
---

## 运行时检索流水线（6 层递进）

用户提问时按以下层级检索，**命中即返回**：

### 第 0 层：指代词快速路径 🏃
用户问题含"刚才/之前/上一条/你刚才说/刚刚" → 直接 `session_search` 定位上下文

### 第 1 层：Holographic 🧠
`fact_store(query=\"关键词\")` 2-3 次 → 命中返回，未命中继续

### 第 2 层：缓存点 📦
检查 `data/{模块}/cache/` 文件 mtime + TTL → 详见 `cache-check` skill

### 第 3 层：知识库 📚
`read_file ~/.hermes/data/knowledge/vault/entities/` + `read_file ~/.hermes/data/knowledge/vault/` → 命中即秒回

### 第 4 层：近期对话 🔍
`session_search(关键词)` → 搜历史上下文

### 第 5 层：网络搜索 🌐
`web_search` → 最后手段

> 详细流程见 `~/.hermes/data/knowledge/vault/00-系统文档/记忆系统使用指南.md` § 四、运行时检索。
> 简化版见 SOUL.md § 信息检索流水线。

---

## 触发条件（宽泛版）

本 skill 在以下**任一**场景触发：

1. 用户明确说"记住/保存/记录/存一下/归档" → 强制执行
2. **完成分析后自检**：这条分析结论需要持久化吗？→ 是则触发
3. **发现踩坑/教训**：这个错误值得记住 → 触发
4. **用户分享新知识**：你学到了一个之前不知道的 → 触发
5. **每日复盘**：cron 触发定期审视新信息是否需要分流

## ⚡ 核心触发：主上引导完成后自动总结

**这是本 skill 最重要的触发场景，不是等主上说"存一下"才动手。**

每次主上引导你完成一项分析/工作后（讨论投资逻辑、debug 系统、梳理框架等等），**自动做以下三件事，不需要问：**

1. **归纳方法**：这次分析用了什么逻辑框架、判断依据、分析方法？把"怎么做的"提炼出来\n2. **DIKW 分流**：方法论→`fact_store`，结构化数据→~/.hermes/data/knowledge/vault/entities/，完整报告→~/.hermes/data/knowledge/vault/\n3. **一步到位**：不要等主上催，当场执行

### 实操口诀

> 分析完，想三句：用了什么方法？有什么数据？能出报告吗？→ 分别存完再收工。

## 常见误区（2026-09-20 校正）

### ❌ 之前错误：动态数据塞进 Hindsight（旧系统）
之前的版本把净值、动量、短期判断存到 Hindsight，导致：
- 过期数据污染（用户一问有色金属PE，从Hindsight翻出旧数据）
- 高频检索被低价值数据占满
- 每次读到过期数据都需要核实，反而增加成本

### ✅ 正确做法：动态数据进 data cache，方法论进 Holographic
- 净值/动量/PE分位 → `data/investment/` 下对应模块的 cache 目录
- 基金操作红线/仓位公式/分析框架 → **Holographic**（大脑可直接用）
- 完整分析报告 → 知识库 + Holographic(索引摘要)

### ❌ 触发条件太窄
之前的版本只在用户说"记住"时触发 → 平时分析完了不触发

### ✅ 自动触发
完成任何实质分析后，自问：这个结论/方法/教训值得持久化吗？

### ❌ DIKW 被 bypass（"记住"走捷径调 memory）

**症状**：用户说"记住之前讨论的内容" → 模型直接调 `memory(action='add')` 倒数据，不经过归纳→三问判断→分流。

**根因链条**：
1. `dikw-memory-flow` skill 的触发条件写了"用户说记住→强制执行"
2. 但 skill 的 frontmatter 有 `triggers: []`（已移除关键词触发，靠 SOUL 驱动）
3. **SOUL.md 中没有对应的强制执行铁律**
4. 模型在"简单指令"压力下走捷径，跳过归纳和三问判断，直接调 `memory`

**修复**：必须在 SOUL.md 铁律中加入类似 P2.1 的强制规则：
```
P2.1 DIKW 强制触发："记住/存一下/保存/记一下"类指令必须先走 DIKW 三问判断，
不得直接调 memory 工具。归纳内容 → 三问分流 → 选工具执行。
```

**教训**：skill 的触发条件写清楚不够 → **SOUL 铁律是执行保障**。模型在"简单指令"压力下会走捷径，需要 system prompt 级的硬约束才能拦住。

### ✅ 正确做法
SOUL.md 铁律 + skill 操作指南 双层保障：铁律不让 bypass，skill 告诉你怎么做。

### ❌ DIKW 三问判断表只放 vault（不注入 context）

**症状**：SOUL.md 仅在"记忆系统"节写了一句"完整定义见记忆系统指南"，三问判断表（会变吗/高频吗/卡片还是书）放在 vault 目录下 → 模型不主动 read_file 就看不到。

**根因**：
1. 三问表放在 `~/.hermes/data/knowledge/vault/00-系统文档/记忆系统使用指南.md` 中
2. vault 需要模型主动 `read_file` 才能获取
3. 在"简单指令"（如"记住"）场景下模型不会主动去 vault 查
4. 结果：DIKW 三问判断形同虚设

**修复**：三问判断表必须直接写进 SOUL.md（每轮注入），三行即可：

```
### DIKW 分流三问（每次分析完成后强制自问）
| 问题 | 答案决定存哪 |
|------|-------------|
| 这个信息会变吗？ | **会变** → data cache（带时间戳） / **不会变** → 大脑或图书馆 |
| 我每次推理都要用吗？ | **高频** → 大脑（`fact_store`） / **偶尔查** → 图书馆（Vault） |
| 它是一张卡片还是一本书？ | **卡片**（单个实体）→ 实体页 `~/.hermes/data/knowledge/vault/entities/` / **体系化** → 图书馆 `~/.hermes/data/knowledge/vault/` |

> 如果拿不准存哪，先存大脑（cheap），fact_feedback 可以校准，fact_store 可以追加。
```

**教训**：**高频行为必须在 SOUL 中定义，不能在 vault 中"等模型去查"**。SOUL 是每轮注入的 system prompt，vault 是主动读文件。模型在指令压力下不会主动探险 vault。

### ✅ 正确做法
- 三问判断表 → SOUL.md（每轮注入）
- 详细操作指南 → skill（本文件，需要时加载）
- 完整文档 → vault（需要时 read_file）

### ❌ 混淆 Knowledge 层与 Wisdom 层

**症状**：把完整文档（SOUL.md、AGENTS.md、记忆系统指南）和从中提炼的方法论 facts 混为一谈。

**案例（2026-06-02 纠正）**：
- 我把 SOUL.md、AGENTS.md 归为 "Wisdom 层"
- 用户纠正：**完整文档属于 Knowledge 层**（可复用的规则/规范），**从文档提炼的方法论 facts 才是 Wisdom 层**（不变的核心原则）

**正确分类**：

| 层级 | 存放 | 内容 |
|------|------|------|
| **Knowledge** | 完整文档文件 | SOUL.md、AGENTS.md、记忆系统指南、部署指南、实体页卡片 |
| **Wisdom** | Holographic（大脑） | 从文档中提炼的 15 条核心方法论 facts（DIKW三问、fact_store用法、铁律、思维协议等） |

**记忆**：文档是"书"，facts 是"书中的原则"。书 → Knowledge，原则 → Wisdom。

### ✅ 正确做法

- 完整文件 → vault/ 或对应路径（Knowledge）
- 提炼原则 → fact_store 大脑（Wisdom）

### ❌ 混淆通用版与本地专用版

**症状**：把通用版模板文件覆盖到本地专用版位置，或反之。

**案例（2026-06-02 纠正）**：
- 四件套通用版（hermes-holographic-*.md）存在 `cache/documents/`
- 本地专用版 SOUL.md、AGENTS.md 在 `~/.hermes/`
- 我执行 `cp 通用版 AGENTS.md → ~/.hermes/AGENTS.md`，覆盖了本地专用版

**正确区分**：

| 类型 | 用途 | 存放位置 |
|------|------|---------|
| **通用版** | 供其他设备部署参考 | `vault/00-系统文档/` 或 `cache/documents/` |
| **本地专用版** | 小明当前正在使用的版本 | `~/.hermes/SOUL.md`、`~/.hermes/AGENTS.md` |

**关键区别**：
- 通用版：去掉"主上"、飞书，投资等专有内容，做成模板
- 本地专用版：包含小明特定配置（飞书、投资、具体基金代码等）

### ✅ 正确做法

- 修改本地专用版前：**先备份**
- 用通用版更新本地版前：**先确认目标文件的用途**
- 通用版模板 → 存 vault（供部署参考）
- 本地专用版 → 保持在 `~/.hermes/` 原位

### ❌ 盲目假设文档通用
当被问"某个文档是否需要修改"时，不要仅凭结构判断。**必须通读全文确认无领域绑定例**——时效性表、目录速查、举例中的专有名词都是隐藏的绑定信号。

### ✅ 正确做法
通读全文后逐项检查：
- [ ] 举例中是否有本单位/领域专用的名词？
- [ ] TTL/有效期表是否假设了特定业务？
- [ ] 目录速查是否硬编码了特定模块路径？
- [ ] 检索规则中的示例是否通用？

## 常见误区补充（2026-06-02 实测）

### ❌ 反模式：网络搜索/凭印象 优先于 实体页

当用户问"XXX 是什么 / XXX 怎么样"时，**不要直接 web_search 也不要凭印象给答案**。先按 DIKW 第 3 层查实体页：

1. `~/.hermes/data/knowledge/vault/entities/funds/<代码>.md`（基金代码）—— 几乎所有用户问过的基金都已建实体页
2. `~/.hermes/data/knowledge/vault/entities/industry/<名称>.md`（行业概念）
3. `~/.hermes/data/knowledge/vault/02-投资研究/` 下的完整报告
4. `~/.hermes/data/knowledge/vault/entities/concepts/` 下的方法论框架

**命中即返回**。命中后再决定是否需要网络验证当前动态数据（第 5 层兜底）。

> **主上纠正案例（2026-06-02）**：
> - 用户问 004433 基金信息 → 我直接给印象答案（"004433 关联有色金属，建议建仓5%"）
> - 主上反问"你不能上网找吗？忘了 DIKW 机制的最后一条了？"
> - 实际 `~/.hermes/data/knowledge/vault/entities/funds/004433.md` 早就存在，规则是 **"净值<1.68 + 动量>45 才建仓"**
> - 当前净值 1.9274、动量 39.4 → **完全不满足建仓条件** → 我的方案"建仓 5%" **严重违反 5-25 报告和实体页双锁定的"等待"规则**
> - 错在没有执行第 3 层就跳到第 5 层

### ❌ 反模式：检索关键词匹配 ≠ 实际文件名/术语一致

Holographic（大脑）检索返回的"关键词"可能是**转写错误**或**谐音替换**。常见案例：

- "华为τ定律" → 实际文件叫"华为韬定律"（谐音替换）
- 检索结果命中后**必须通读实际文件确认**实际术语和定义，不能直接用检索到的关键词作为标准

> **主上纠正案例（2026-06-02）**：
> - Holographic 反复显示"华为τ定律"
> - 实际 `~/.hermes/data/knowledge/vault/02-投资研究/华为韬定律与有色金属投资分析.md` 用的是"韬"
> - 含义确实是 τ 定律（信号时延常数），但命名用了"韬"
> - 教训：双标"华为韬（τ）定律"避免再混，但**索引时必须确认实际文件名**

### ✅ 正向习惯：每次检索后自觉评估（反馈回路激活）

> 对应 SOUL.md 反馈校准 → 每次检索后自觉评估（习惯流程）

反模式的修复是「发现偏差时处理」（被动），这个习惯是「每次检索后主动检查」——两者的差异决定了反馈回路能跑多快。

**流程**（已写入 SOUL.md，skill 层作为提醒）：
每次 `fact_store(search)` 返回结果后，按顺序快速过一遍：
1. 结果中有准确可用的吗？ → `fact_feedback(helpful, fact_id=xxx)`
2. 结果中有过时/错误的吗？ → `fact_feedback(unhelpful, fact_id=xxx)`
3. 全部正常或不相关 → 跳过（<1 秒）

**为什么正确的事实也要标记 helpful**：
信任分不是二分的（0/1），而是连续值。正确事实收到 helpful 能提升它在排序中的权重。如果只有错误事实被降权、正确事实从不升权，trust_score 分布会整体下移。

**闭环形成的信号**：
当 `fact_store(search)` 返回结果中 `retrieval_count` 和 `helpful_count` 开始出现 >0 的值，说明反馈回路已经激活。持续 7-14 天的实践足以让 TOP 100 高频事实的 trust_score 分布可靠起来。

### ✅ 自动化补充：cron 驱动的事实信任分校准

> 2026-06-02 新增：`agent/fact_feedback_loop.py` — 直接操作 SQLite，不依赖 Agent tool 调用

**手动反馈的局限**：Agent 在对话中不会主动调 `fact_feedback`（上述"自觉评估"在实际执行中几乎为 0）。
**解决方案**：绕过 Agent 推理层，用确定性统计规则自动校准。

`fact_feedback_loop.py` 的三条规则：

| 规则 | 条件 | 动作 | 执行者 |
|------|------|------|--------|
| ① 降权 | retrieval_count ≥ 3 AND helpful_count = 0 | trust -= 0.1 | cron 每周六 11:00 |
| ② 升权 | helpful/retrieval > 30% | trust += 0.05 | cron 每周六 11:00 |
| ③ 衰减 | 零检索 > 14 天 | trust ×= 0.95 | cron 每周六 11:00 |

**手动 vs 自动的分工**：
- **自动（cron）**：批量统计校准——降权低质量、升权高质量、衰减零检索
- **手动（Agent）**：实时纠偏——发现过时/错误事实时，当场 `fact_feedback(unhelpful)` 立即降权

> 详见 skill `fact-feedback-loop` 与 `agent/fact_feedback_loop.py`

---

### ❌ 反模式：记忆引擎切换后，新工具存在但未被激活

**症状**：切换记忆引擎（如 Hindsight → Holographic）后，新系统带来了新工具（如 `fact_feedback`），但这些工具在切换后从**未被使用过**——模型继续以旧系统的方式工作，新能力的校准/反馈回路处于空转状态。

**检测信号**：`fact_store` 搜索结果中全部 facts 的 `retrieval_count = 0` 和 `helpful_count = 0` → 说明 `fact_feedback` 从未被触发过。这不是正常状态——校准机制存在但死着。

**修复（2026-06-02 已落实）**：
1. **自动化方案**：`agent/fact_feedback_loop.py`（cron 每周六 11:00）直接操作 SQLite，用三条确定性规则自动校准信任分——绕过 LLM 推理层，100% 命中
2. **手动方案**：发现错误/过时的 fact 后，**立即当场执行** `fact_feedback`，不等、不问、不拖

```json
// 发现过时/错误 fact → 当场降权
fact_feedback(action="unhelpful", fact_id=xxx)

// 发现高质量有用 fact → 当场升权
fact_feedback(action="helpful", fact_id=xxx)
```

**教训**：切换记忆引擎后，**第一个检查项不是"工具是否注册"，而是"工具是否被实际使用"**。新工具注册了不等于激活了——如果 Agent 不会主动调它，就必须用 cron 自动化绕过 Agent 推理层。

### ❌ 反模式：主上要求"核实"时跳过实体页查证

当主上说"**先帮我核实一下之前的分析/建议是否合理**"时，**不能凭印象做反向验证**。必须：

1. 列出所有相关的 `~/.hermes/data/knowledge/vault/entities/*.md`
2. 通读实体页的"操作计划/止损/止盈/建仓条件"段
3. **逐条对照之前的建议是否触发这些条件**
4. **如果违反，**直说"违反 X 规则"**，不要绕弯**

> **主上纠正案例（2026-06-02）**：
> - 用户说"确认之前，你先帮我核实一下前期的分析是否正确，当前的建议是否合理"
> - 我做了"读实体页"的动作后，发现 2 个严重违规：
>   1. 建议"建仓 004433 5%"违反实体页双条件触发规则
>   2. 记错止盈线（"涨 15%" 实际是 "≥+20%"）
> - **承认错误的回报**：主上看到"诚实承认违规"后立即进入"修正方案"模式，没追究过程

### ❌ 反模式：更新铁律编号后，跨引用"内容错位"

**症状**：SOUL.md 铁律重排编号（如 P1.5→P1.4、P2.5→P2.1）后，所有 skill 中的引用编号都已更新正确，但**引用的规则描述与实际铁律内容不匹配**。

**案例（2026-06-02 重排）**：
- `knowledge-base/SKILL.md`：`SOUL P1.4 铁律：投资类查询必须先查实体页`
- 实际 P1.4 = **路径合规**（写入文件前查 AGENTS.md 目录规范）
- "先查实体页"这条行为属于**信息检索流水线第3层**，不是铁律

**正确做法**：更新引用时，必须同时核对两件事：
1. 编号是否正确 → ✅ 找到对应行
2. **描述内容是否与编号对应** → ❌ 这个常被漏掉

**检查口诀**：
```
改编号，找三处：
① 本文件铁律表    → 改好
② skill 引用编号  → 改对数字
③ 引用描述内容    → 也要改（最常见的漏项）
```

**教训**：编号对齐是比内容对齐更容易的事——先改了编号就觉得"完成了"，但内容错位在运行时才是真正出问题的地方。一个 skill 说"P1.4 铁律规定先查实体页"，新模型读到 P1.4 发现是"路径合规"，两个不符，就会违反直觉。

### ❌ 反模式：写完必提规则只放在 SOUL/skill/指南 — 不够

**症状**：把"写完 vault 文档后必须提炼 1-3 条方法论到 fact_store"写在 SOUL.md（system prompt）、记忆系统指南.md、dikw-memory-flow SKILL.md 三处。但 Agent 在工具调用密集的场景下可能忽略 system prompt 里的规则，直接给出回复而不提炼。

**根因**：
1. SOUL.md 铁律在长上下文（20+ 轮工具调用后）被注意力稀释
2. skill 在 auto-trigger 后是前置注入到 user_message 中，容易被覆盖
3. 记忆系统指南（vault 文件）需要 Agent 主动 read_file 才能加载
4. 三者都需要 Agent **主动记住并执行**，没有任何强制力

**修复（2026-06-02 commit cafff3c4b）**：
- `agent/tool_executor.py` 新增 `_inject_vault_duty()` 函数
- 在 write_file 工具执行完毕、结果追加到 messages 之后检查路径
- 如果路径包含 `vault/` 组件，自动在 tool result 尾部注入 [DUTY] 提醒
- 顺序路径 + 并发路径各加一行调用

**工作原理**：工具执行完成后 `messages[-1]` 是 tool result → [DUTY] 直接追加到 content → LLM 下轮必然读到（在 messages 中，不在 system prompt 里可以稀释）

**教训**：
- SOUL 是**指导性**规则，长上下文中注意力衰减
- Skill 是**匹配触发**，依赖命中条件
- 源码钩子是**硬编码强制力**，在工具执行层注入，不依赖 Agent 注意力
- 需要**确定性执行**的行为必须上源码级钩子

### ✅ 正确分层保障

| 保障层 | 触发率 | 定位 |
|--------|--------|------|
| SOUL.md 铁律 | ~60% | 指导性规则 |
| Skill 自动触发 | ~70% | 关键词匹配触发 |
| **源码钩子（tool_executor.py _inject_vault_duty）** | **100%** | 工具执行层强制注入 |
| **四层自愈闭环整体** | **系统层** | ①自动触发 → ②容量管理 → ③反馈校准 → ④vault-write 强制提炼 |

**判断标准**：漏执行有什么后果？
- 信息链条断裂（K→W）→ 必须上源码钩子
- 资金损失/系统故障 → P0 铁律 + 源码钩子 + cron 复盘

---

### 落地口诀

> **问具体代码/概念** → 先 `~/.hermes/data/knowledge/vault/entities/` 查 → 命中就够；不够再 `~/.hermes/data/knowledge/vault/`；还不够再 `session_search`；最后才 `web_search`
> **核实旧建议** → 列实体页 → 通读操作规则 → 逐条对照 → 违规就直说
> **术语转写** → 命中 Holographic 后**通读实际文件确认**，不要用关键词当标准

---

## 验证

每次执行后自问：
- [ ] 我判断这是 D/I/K/W 哪层？
- [ ] 会变还是不变？（动态→cache / 不变→Holographic/知识库）
- [ ] 访问频率高还是低？（高频→大脑 / 低频→知识库）
- [ ] 有已有缓存点可以直接用吗？
- [ ] 告知用户存储位置了吗？
- [ ] **（新增）涉及具体代码/概念时，是否先查了 `~/.hermes/data/knowledge/vault/entities/`？**
- [ ] **（新增）主上要求"核实"时，是否逐条对照了实体页操作规则？**
- [ ] **（新增）Holographic 关键词是否通读了实际文件确认术语一致？**
- [ ] **（新增）本 skill 中引用的工具签名（fact_feedback、fact_store 等）是否与实际 available tools 一致？不一致则立即 patch。**
- [ ] **（新增）切换记忆引擎后，检查新工具是否被实际使用**：`fact_feedback` 的 `retrieval_count` 是否全部为 0？是 → 主动触发第一次校准
- [ ] **（新增）修复工具签名后，是否同步检查了 `cache/documents/` 下的通用模板文件？** 四件套模板独立于本地文件，需要单独更新。
- [ ] **（新增）更新 SOUL.md 铁律编号后，是否检查了所有 skill 引用的"描述内容"与编号匹配？** 编号对齐 ≠ 内容对齐，容易漏改。
- [ ] **（新增）涉及通用版模板更新时，是否区分了通用版和本地专用版？** 通用版存 vault，本地专用版保持在 ~/.hermes/ 原位。
- [ ] **（新增）四层自愈闭环的第④层（vault-write 强制提炼）是否就位？** agent/tool_executor.py 中 _inject_vault_duty() 必须在两个执行路径（顺序+并发）各加一行调用。

## Legacy System Data Migration (Dead DB Recovery)

> **何时用**：旧记忆系统已下线（daemon 停了、token 过期、API 挂了），但数据在 DB 文件或 Docker volume 里完好，需要提取并迁移到当前 memory provider（Holographic）。
>
> 典型场景：Hindsight PG daemon 停用、token 永久失效、API 500 持续不可恢复 → 只能从 Docker volume 直接读 DB。

### 迁移原则：DIKW 分层 + 保守迁移

| 原则 | 说明 |
|------|------|
| **少即是多** | 旧系统存了大量过期事件日志、重复会话摘要。D 层 99% 不值得迁，只迁 W 层方法论 |
| **先查重** | 存储前先 `fact_store(query=...)` 查现有 Holographic 是否已有同类内容，避免重复 |
| **不迁移配置** | 旧系统的 provider 特有配置（API key、URL、model name）毫无价值，直接跳过 |
| **source 标记** | 迁移后的事实加 `source` 标记（如 `source="migrated-from-hindsight"`）方便追溯 |

### Step 1: 挂载死 DB

```bash
# PG volume → 临时容器
docker run -d --name temp-pg \
  -v hindsight-pgdata:/var/lib/postgresql/data \
  -e POSTGRES_PASSWORD=temp \
  -p 5433:5432 \
  postgres:18

# SQLite 直连（如 Hindsight 用 SQLite 而非 PG）
sqlite3 /path/to/legacy.db
```

### Step 2: 盘点数据

```python
# 查表结构
# PG: \dt → memory_units 表
# 查记录数、时间范围、内容特征
cur.execute("SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM memory_units")
cur.execute("SELECT DISTINCT category FROM memory_units")
```

### Step 3: DIKW 三问全量分类

对每条记录/每个分组跑三问：

| 问题 | W (值得迁) | K (值得迁) | D (跳过) |
|------|-----------|-----------|---------|
| 会变吗？ | ❌ 不变（方法论、框架、原则） | 可能不变（结构定义） | ✅ 会变（事件日志、快照） |
| 跨 session 有用吗？ | ✅ 高频（下次推理就要用） | 偶尔查 | ❌ 已过期，仅本 session 相关 |
| 是卡片还是体系化？ | — | 卡片（结构化定义） | 废纸（临时笔记） |

**关键判断**：3 秒内想不起来为什么存这条 → 直接跳过。99% 的旧数据是"当时有用但早过时了"。

### Step 4: 查重 + 写入

```python
# 对每条 W 层候选：
# 1. 先用 fact_store(query=...) 查现有库是否有同类内容
# 2. 有 → 对比 content，新内容补到现有 fact（用 fact_feedback 标记落差）
# 3. 无 → fact_store(content=..., query=..., source="migrated-from-xxx")
```

### Step 5: 验证

```python
# 搜每条新存的事实
print(ms.search_facts("关键词"))  # 应在 Top-K 中出现
```

### 本案实战数据（Hindsight PG → Holographic）

- **存量**：264 条 `memory_units`（PG 18.1.0 Docker volume）
- **分类结果**：W=3, K=0, D=261
- **跳过原因**：D 层包括：每日会话摘要（过期）、重复会议记录、已 resolve 的故障事件、provider 特有配置（URL/token/model name）
- **3 条 W 方法论**：API 配额管理原则、压缩模型配置原则、API 配额诊断方法
- **耗时**：从 docker start → 分析 → 迁移完成约 8 分钟（含 5 分钟 DIKW 分类思考）
- **教训**：旧系统 264 条中只迁 3 条（~1%）—— 说明**不是所有历史数据都值得迁移**。大多数记忆是"当时有用"而非"永远有用"。

## 相关文档

- `references/investigation-analysis-verification.md` — **投资分析核实 4 步法**
- `references/dikw-audit-checklist.md` — **DIKW 合规审计清单**（7维度系统审计方法论）
- `references/hermes-holographic-deploy-guide.md` (memory-system-architecture skill) — 从零部署完整教程（含 DIKW 分流 + 四层自愈闭环 + vault-write 强制提炼）
- `~/.hermes/data/knowledge/vault/00-系统文档/记忆系统使用指南.md` — **记忆系统综合指南**（大脑+图书馆、DIKW、分流流程、检索规则、时效管理，一页讲清）
- SOUL.md § 信息检索流水线：Agent 行为规则（6层递进检索）
- 知识库文档：~/.hermes/data/knowledge/vault/00-知识库说明.md
- 探风/挖呗共享缓存：data/investment/wab/cache/（动量+PE+行情数据）
- 评分历史：data/investment/scores/（季度归档，含时值模型评分）
