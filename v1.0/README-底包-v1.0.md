# Hermes Agent Holographic 版 — 完整记忆系统底包（含四层自愈闭环）

> 面向**零基础 Agent** 的完整版底包。
> 记忆引擎使用 Holographic（Hermes 内置插件），零 Docker 依赖。
> ⚠️ **本版本特别针对中文场景优化**——包含 FTS5 CJK 字符间距补丁 + 完整反馈闭环。

---

## 文件清单

> ⚠️ **改名警告**：以下文件在部署时**必须改名**（去掉版本后缀）。直接复制带 `hermes-holographic-完善版` 的文件名到目标路径，Agent 会因为找不到 `SOUL.md` / `AGENTS.md` 而无法加载人格和目录规范。

| 源文件（下载后） | 改名后（部署位置） | 作用 |
|------|------|---------|
| `hermes-holographic-soul-完善版.md` | → `~/.hermes/**SOUL.md**` | Agent 人格定义（铁律/思维协议） |
| `hermes-holographic-agents-完善版.md` | → `~/.hermes/**AGENTS.md**` | 工作区目录规范 |
| `hermes-holographic-记忆系统指南-完善版.md` | → `~/.hermes/data/knowledge/vault/00-系统文档/**记忆系统使用指南.md**` | DIKW 记忆系统完整 SOP |
| `agent/skill_auto_trigger.py` | → `~/.hermes/hermes-agent/agent/**skill_auto_trigger.py**` | 技能自动触发（源码层） |
| `agent/tool_executor.py`（patch） | → `agent/tool_executor.py` 中 `_inject_vault_duty()` | vault-write 强制提炼（源码级，100% 触发） |
| `agent/fact_feedback_loop.py` | → `~/.hermes/hermes-agent/agent/**fact_feedback_loop.py**` | 信任分自动校准（源码层） |
| `skills/system/memory-capacity-management/SKILL.md` | → `~/.hermes/skills/system/memory-capacity-management/**SKILL.md**` | **四核心文件**容量管理 & DIKW 分流 |
| `skills/system/fact-feedback-loop/SKILL.md` | → `~/.hermes/skills/system/fact-feedback-loop/**SKILL.md**` | 反馈闭环技能文档 |

---

## 完整架构

```
┌────────────────────────────────────────────────────────────┐
│                  Hermes Agent (x86/ARM64)                    │
├──────────────────────┬─────────────────────────────────────┤
│  SOUL.md             │  人格层：铁律、思维协议               │
│  AGENTS.md           │  基础设施层：目录规范                 │
│  记忆系统使用指南.md   │  记忆系统层：DIKW + Holographic      │
├──────────────────────┴─────────────────────────────────────┤
│                                                             │
│  记忆引擎：Holographic（Hermes 内置插件）                    │
│    └─ SQLite（memory_store.db）[全局共享，跨 session]       │
│       ├─ FTS5 全文索引 ⭐（自动每轮检索，权重 0.4）         │
│       │   └─ 已打中文补丁 _space_cjk() ✅ 中文可用          │
│       ├─ Jaccard 重排（模糊容错，权重 0.3）                 │
│       └─ HRR 代数（显式 probe 检索，权重 0.15-0.3）         │
│                                                             │
├──────────────────────┬─────────────────────────────────────┤
│        四层自愈闭环    │                                       │
├──────────────────────┼─────────────────────────────────────┤
│  ① 技能自动触发        │  agent/skill_auto_trigger.py        │
│                       │  → 用户消息匹配 triggers 关键词时     │
│                       │    自动注入 skill 到 LLM 上下文       │
├──────────────────────┼─────────────────────────────────────┤
│  ② 容量管理            │  memory-capacity-management skill    │
│                       │  + cron **每日 9:00** （no_agent 静默）│
│                       │  → SOUL/MEMORY/USER/AGENTS >85% 时   │
│                       │    自动触发 DIKW 分流                 │
├──────────────────────┼─────────────────────────────────────┤
│  ③ 反馈闭环            │  agent/fact_feedback_loop.py        │
│                       │  + cron 每周六 11:00                │
│                       │  → 基于统计规则自动校准信任分        │
├──────────────────────┼─────────────────────────────────────┤
│  ④ vault-write 强制提炼│  agent/tool_executor.py (源码级)     │
│                       │  → write_file 到 vault/ 后自动       │
│                       │    在 tool result 中注入 [DUTY] 提醒  │
│                       │  → 100% 触发，不依赖 Agent 记忆       │
└──────────────────────┴─────────────────────────────────────┘

零外部服务依赖 ✅
ARM64/x86 原生运行 ✅
跨 session 全局共享 ✅（无需固定 session ID）
中文检索 ✅（需打 _space_cjk() 补丁）
技能自动触发 ✅（关键词匹配注入）
信任分自动校准 ✅（SQLite 直连，免 tool 调用）
vault-write 强制提炼 ✅（源码级硬钩子，100% 触发）

**完整信息流闭环**：指令 → Agent → Skill加载 → 大脑(方法论) → 图书馆(踩坑→知识库→缓存→网搜) → **工具调用决策** → 执行/处理 → 结果/反馈 → 迭代方法论
```

---

## 前置条件检查清单

| 项目 | 检查命令 | 通过标准 | 如果失败怎么办 |
|------|---------|---------|--------------|
| Hermes Agent | `hermes version` | v0.10+ | 先升级 Hermes |
| Python | `python3 --version` | 3.10+ | Hermes 自带 |
| numpy（强烈推荐） | `python3 -c "import numpy; print('OK')"` | 输出 OK | `pip install numpy` / 在 venv 中安装 |
| SQLite | `python3 -c "import sqlite3; print('OK')"` | 输出 OK | 内置，无需安装 |

> **无 numpy = HRR 降级为纯 FTS5+Jaccard**，检索能力下降 ~30%。强烈建议安装。

---

## 部署步骤

### Step 1：放文件

```bash
# 复制三件套到对应位置
cp hermes-holographic-soul-完善版.md ~/.hermes/SOUL.md
cp hermes-holographic-agents-完善版.md ~/.hermes/AGENTS.md

# 创建记忆系统指南目录
mkdir -p ~/.hermes/data/knowledge/vault/00-系统文档
cp hermes-holographic-记忆系统指南-完善版.md \
   ~/.hermes/data/knowledge/vault/00-系统文档/记忆系统使用指南.md
```

### Step 2：配置记忆插件

编辑 `~/.hermes/config.yaml`，找到或添加 `plugins:` 段：

```yaml
plugins:
  # ... 其他插件 ...

  memory_provider: holographic               # ← 启用 Holographic 插件

  hermes-memory-store:                         # ← 注意 key 名
    db_path: ~/.hermes/memory_store.db        # SQLite 数据库路径
    auto_extract: 'false'                     # 不自动提取（用 SOUL.md 三问流程）
    default_trust: '0.5'                      # 新事实默认信任分
    min_trust_threshold: '0.3'                # 检索过滤下限
    temporal_decay_half_life: '0'             # 方法论不过期
    hrr_weight: 0.15                          # HRR 权重（中文场景推荐 0.15）
```

### Step 3：部署技能自动触发系统（源码修改）

这是唯一需要改源码的步骤。替换 `conversation_loop.py` 中的注入点：

```bash
# 复制核心模块
cp agent/skill_auto_trigger.py ~/.hermes/hermes-agent/agent/skill_auto_trigger.py

# 确认文件已就位
python3 -c "from agent.skill_auto_trigger import auto_load_triggered_skills; print('✅ skill_auto_trigger ready'); print(auto_load_triggered_skills('测试记忆满了'))"
```

然后在 `~/.hermes/hermes-agent/agent/conversation_loop.py` 中，找到 L571 附近（`_should_review_memory` 判断之后、`user_msg` 构造之前），插入以下 9 行：

```python
    # Auto-trigger skills by keyword match in user message
    try:
        from agent.skill_auto_trigger import auto_load_triggered_skills
        skill_content = auto_load_triggered_skills(user_message)
        if skill_content:
            user_message = skill_content + "\n\n---\n\n" + user_message
    except Exception:
        pass  # best-effort: auto-trigger failure must not break conversation
```

```bash
# 验证语法
python3 -c "import py_compile; py_compile.compile('~/.hermes/hermes-agent/agent/conversation_loop.py', doraise=True)" 2>/dev/null && echo "✅ syntax OK"
```

### Step 4：部署反馈闭环模块

```bash
# 复制核心模块
cp agent/fact_feedback_loop.py ~/.hermes/hermes-agent/agent/fact_feedback_loop.py

# 验证运行
python3 -m agent.fact_feedback_loop --report
```

### Step 5：部署技能文件

```bash
# 复制技能目录
cp -r skills/system/memory-capacity-management ~/.hermes/skills/system/
cp -r skills/system/fact-feedback-loop ~/.hermes/skills/system/
```

### Step 6：配置 Cron 任务

在第一个对话中，Agent 会自动注册以下 cron 任务。如果不自动触发，可以手动执行：

```python
# 在 Agent 对话中执行：
# 【容量监控】每日 9:00 静默检查 SOUL/MEMORY/USER/AGENTS 四个核心文件
cronjob(action='create', name='core-file-capacity-monitor',
        script='check_core_memory_capacity.py',
        schedule='0 9 * * *',
        no_agent=True)
# 全部 <70% → 静默（空 stdout）；任一 >85% → 推送告警，建议执行 DIKW 分流

# 【信任分校准】每周六 11:00
cronjob(action='create', name='fact-feedback-calibrate',
        schedule='0 11 * * 6',
        prompt='执行 Holographic 信任分校准：dry-run → apply → 推送报告...',
        skills=['fact-feedback-loop'])
```

### Step 7：重启 Gateway

```bash
kill <gateway-pid>
hermes gateway run &
```

### Step 8：完整验证

```bash
# 1. 验证插件激活
# 在会话中输入：
fact_store(content="系统就绪时间", query="系统 就绪 状态", source="verification")
fact_store(query="系统")

# 2. 验证技能自动触发
# 在会话中输入："整理记忆" — 应自动匹配 memory-capacity-management skill 的 triggers

# 3. 验证反馈闭环
python3 -m agent.fact_feedback_loop --report

# 4. 验证 cron 已注册
cronjob(action='list')
```

---

## ⭐ 关键步骤：FTS5 中文分词补丁

**这是针对中文场景的必做步骤。** 不执行此步骤，所有中文检索（搜"建仓"、"基金"等）都会返回 0 条。

### 问题背景

FTS5 默认的 `unicode61` tokenizer 不分割连续中文字符——"分批建仓策略"被当做一个 token 而非四个独立词。

### 解决方案（3 分钟完成）

**Step A：备份**

```bash
cp ~/.hermes/hermes-agent/plugins/memory/holographic/store.py \
   ~/.hermes/hermes-agent/plugins/memory/holographic/store.py.bak
```

**Step B：添加 `_space_cjk()` 函数**

在 `store.py` 中，import 区域后面插入以下代码：

```python
import re  # 如果已有则不需要重复

_CJK_PATTERN = re.compile(r'[\u4e00-\u9fff]')

def _space_cjk(text: str) -> str:
    """Insert spaces between consecutive CJK characters for FTS5 unicode61."""
    if not _CJK_PATTERN.search(text):
        return text
    result = re.sub(r'([\u4e00-\u9fff])(?=[\u4e00-\u9fff])', r'\1 ', text)
    result = re.sub(r'([\u4e00-\u9fff])([^\u4e00-\u9fff\s])', r'\1 \2', result)
    result = re.sub(r'([^\u4e00-\u9fff\s])([\u4e00-\u9fff])', r'\1 \2', result)
    return result
```

**Step C：修改 FTS5 写入路径（6 处）**

搜索 `store.py` 中所有写入 `facts_fts` 的地方，对 content 应用 `_space_cjk()`：

| 原代码 | 改为 |
|--------|------|
| `cursor.execute("INSERT INTO facts_fts ... VALUES (?, ?)", (fact_id, content))` | `fts_content = _space_cjk(content); ...(fact_id, fts_content)` |
| 所有直接传 content 到 facts_fts 的地方 | 都过一遍 `_space_cjk()` |

**Step D：重建 FTS5 索引**

```bash
cd ~/.hermes
kill $(pgrep -f 'hermes.*gateway')

python3 << 'PYEOF'
import sqlite3, re
_CJK = re.compile(r'[\u4e00-\u9fff]')
def _space(text):
    if not _CJK.search(str(text)): return text
    text = re.sub(r'([\u4e00-\u9fff])(?=[\u4e00-\u9fff])', r'\1 ', text)
    text = re.sub(r'([\u4e00-\u9fff])([^\u4e00-\u9fff\s])', r'\1 \2', text)
    text = re.sub(r'([^\u4e00-\u9fff\s])([\u4e00-\u9fff])', r'\1 \2', text)
    return text

conn = sqlite3.connect('memory_store.db')
conn.execute("DROP TABLE IF EXISTS facts_fts")
conn.execute("CREATE VIRTUAL TABLE facts_fts USING fts5(content, tags)")
for row_id, content, tags in conn.execute("SELECT rowid, content, tags FROM facts"):
    conn.execute("INSERT INTO facts_fts (rowid, content, tags) VALUES (?, ?, ?)",
                 (row_id, _space(content or ""), tags))
conn.commit()
count = conn.execute("SELECT COUNT(*) FROM facts_fts").fetchone()[0]
print(f"FTS5 rows: {count}")
conn.close()
PYEOF

hermes gateway run --replace
```

### 验证 FTS5 中文搜索

```bash
sqlite3 ~/.hermes/memory_store.db "SELECT COUNT(*) FROM facts_fts WHERE facts_fts MATCH '\"建 仓\"';"
```
预期 ≥3 条命中。

---

## 四层自愈闭环详解

### ① 技能自动触发（agent/skill_auto_trigger.py）

**原理**：在 `conversation_loop.py` 的用户消息构造前注入钩子，扫描所有 `~/.hermes/skills/**/SKILL.md` 的 frontmatter 中 `triggers` 字段，消息包含关键词时自动注入 skill 内容。

**SKILL.md 格式示例**：
```yaml
---
name: my-skill
triggers: [记住, 保存, 整理, memory满]
---
```

**使用效果**：
```
用户说"整理记忆"
  → skill_auto_trigger.py 匹配 triggers ["整理记忆"]
  → 自动注入 memory-capacity-management 的完整 SKILL.md 内容到消息头部
  → Agent 拿到 skill 指令后按流程执行
```

**设计原则**：
- Best-effort：整个钩子包裹在 try/except 中
- 纯关键词匹配（`keyword in msg_lower`），简单可靠
- 无 triggers 字段的 SKILL.md 不受影响
- 原消息保留在 skill 内容之后（`---` 分隔）

---

### ② MEMORY.md 容量管理（memory-capacity-management skill + cron）

**检测阈值**：

| 等级 | 占用率 | 动作 |
|------|--------|------|
| 🟢 正常 | <70% | 静默 |
| 🟡 注意 | 70-85% | 提醒 |
| 🟠 告警 | 85-95% | **自动 DIKW 分流** |
| 🔴 满仓 | >95% | 无法添加，强制清理 |

**自动分流流程**（每日 9:00 cron no_agent 检测，超限后触发分流）：
1. 调 `memory` 工具读取全部条目和占用率
2. 逐条 DIKW 四问判断（会变吗？高频用？卡片还是书？**踩坑经验？**）
3. W 层→`fact_store` 存大脑，K 层→`write_file` 到 vault
4. 踩坑结论→`fact_store(source="lesson")`，完整经过→`vault/踩坑记录/`
5. 替换为一行索引（`[分类-关键词] | 一句话 + 详见路径`）
6. 验证占用降至 <60%

**手动触发**：用户消息包含"memory满"、"整理记忆"、"容量管理"等 triggers 关键词时自动注入 skill。

---

### ③ 信任分自动校准（agent/fact_feedback_loop.py + cron）

**核心规则**（直接操作 SQLite，无需 tool 调用）：

| 规则 | 条件 | 动作 | 含义 |
|------|------|------|------|
| 降权 | retrieval_count ≥ 3 AND helpful_count = 0 | trust -= 0.1 | 频繁检索但从未有用→低质量 |
| 升权 | helpful / retrieval > 30% | trust += 0.05 | 检索后常被标记有用→高质量 |
| 衰减 | created_at > 14天 AND retrieval = 0 | trust *= 0.95 | 超过两周未检索→低价值 |
| 保护 | — | trust ∈ [0.05, 0.95] | 防止极端值 |

**运行方式**：
```bash
# 查看健康报告
python3 -m agent.fact_feedback_loop --report

# dry-run 预览
python3 -m agent.fact_feedback_loop --calibrate

# 实际校准
python3 -m agent.fact_feedback_loop --calibrate --apply
```

**自动校准**：cron `fact-feedback-calibrate` 每周六 11:00 dry-run → 评估 → apply → 推送报告。

---

## 使用要点

| 操作 | 命令 | 说明 |
|------|------|------|
| 记事实 | `fact_store(content="原则", query="关键词1 关键词2")` | **中文 query 加空格分隔** |
| 搜记忆 | `fact_store(query="关键词")` | 同上，关键词加空格 |
| 手动反馈 | `fact_feedback(action=helpful, fact_id=...)` | 手动校准信任分 |
| 自动校准 | `python3 -m agent.fact_feedback_loop --calibrate --apply` | 批量统计校准 |
| 查看反馈健康 | `python3 -m agent.fact_feedback_loop --report` | 事实库统计报告 |
| 查看容量 | `memory` 工具（不带参数） | 查看 MEMORY.md 占用率 |
| 触发容量整理 | 说"整理记忆"或"memory满" | 自动注入容量管理 skill |
| 搜不到 | 换同义词再试 → `session_search` → `read_file MEMORY.md` | 7+1 层流水线 |
| 中文搜不到 | `fact_store(query="建 仓")`（字间加空格） | FTS5 中文分词限制 |
| 详细操作 | 见 `记忆系统使用指南.md` | 完整 SOP |

### 每次新建会话的固定流程

```
1.  fact_store(query="关键词 覆盖 当前 任务 领域")  # 搜索相关记忆
2.  read_file MEMORY.md + USER.md + TODO.md          # 读核心文件
3.  如果有 last_moment.md → read_file 恢复上下文
4.  回复用户
```

> ⚠️ 以上步骤已打包到 SOUL.md 的「会话初始化」铁律中，Agent 会自动执行。

---

## 通用版文件与本地版的区别

本包提供的是**通用版模板**，部署后需要根据实际情况修改：

| 文件 | 通用版内容 | 需要本地化的地方 |
|------|-----------|----------------|
| SOUL.md | 铁律、思维协议、DIKW 三问、四层自愈闭环引用 | 名字、主人、通信平台（飞书/Telegram/其他） |
| AGENTS.md | 目录规范 | 路径、项目名 |
| 记忆系统使用指南.md | DIKW 四层模型、检索流水线、HRR 编码策略、反馈闭环 | —（基本通用） |
| skill_auto_trigger.py | 自动触发核心逻辑 | —（纯逻辑，无需修改） |
| fact_feedback_loop.py | 信任分校准逻辑 | —（纯逻辑，无需修改） |

---

## 常见问题

### Q：第一次启动就发现搜不到中文？
A：这是正常的。必须打上 FTS5 中文补丁（见「关键步骤」章节）。

### Q：DB 在哪里？文件多大？
A：`~/.hermes/memory_store.db`。7000 条事实约 105MB（含 FTS5 索引）。

### Q：技能自动触发不工作？
A：检查三点：① `agent/skill_auto_trigger.py` 是否在正确路径；② `conversation_loop.py` 是否已打 9 行补丁；③ SKILL.md 的 `triggers` 字段是否存在。

### Q：反馈闭环 cron 需要手动先跑一次吗？
A：首次部署建议手动跑一次初始化校准：`python3 -m agent.fact_feedback_loop --calibrate --apply`。

### Q：cron 任务怎么确认运行正常？
A：在对话中执行 `cronjob(action='list')` 查看所有 cron 的状态。

### Q：我想迁移已有的 Hindsight 记忆？
A：参考记忆系统指南的「DIKW 分流迁移」章节。核心原则：只迁移方法论（W 层）和结构化知识（K 层），事件日志丢弃。

### Q：numpy 装不上怎么办？
A：检查 venv 环境：`source ~/.hermes/hermes-agent/.venv/bin/activate && pip install numpy`。如果实在装不上，HRR 降级为纯 FTS5+Jaccard，检索能力下降约 30%。

---

## 版本兼容

| 组件 | 最低版本 | 备注 |
|------|---------|------|
| Hermes Agent | v0.10+ | 需要 Holographic 插件支持 |
| Python | 3.10+ | 推荐 3.11+ |
| skills 系统 | — | 自动触发需要 v2026.5.29.2+（修改 conversation_loop.py 的权限） |
| fact_feedback_loop.py | — | 独立运行，无版本依赖 |

---

## CHANGELOG

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-02 | v3 | 新增四层自愈闭环（技能自动触发 + 容量管理 + 反馈闭环 + vault-write 强制提炼），重构 README 架构 |
| 2026-05-31 | v2 | 完善版：新增 DIKW 三问、HRR 编码策略、FTS5 中文补丁 |
| 2026-05-12 | v1 | 初版：基础三件套（SOUL + AGENTS + 记忆系统指南） |
