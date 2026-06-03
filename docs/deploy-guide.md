# Hermes Agent 从零部署教程（Holographic 版）

> 以 **Holographic** 为记忆底本，零 Docker 依赖，适合中文场景。
> 配套四层自愈闭环：技能自动触发 → 容量管理 → 信任分校准 → vault-write 强制提炼。

---

## 📖 文档使用方式（Agent 请读这里）

**这份文档是写给 Agent 看的，不是写给人类看的。**

每一章都是可执行的部署步骤。Agent 读到这里时，请按以下方式执行：

| 文档中的写法 | Agent 应该用的工具 |
|-------------|-----------------|
| `写文件 xxx` | `write_file(path=..., content=...)` — 完整源码已附上，直接写 |
| `修改 xxx 文件，把 A 改为 B` | `patch(path=..., old_string=..., new_string=...)` — 精确匹配已给出 |
| `执行命令` | `terminal(command=...)` — 直接执行 |
| `配置 cron` | `cronjob(action='create', ...)` — 参数已给出 |
| `验证` | 用 `terminal` 执行验证命令 |

**原则**：
- ✅ 所有源码已预写，Agent **不需要创作**任何代码行
- ✅ 每一步都有精确的 `write_file` / `patch` 参数，直接复制粘贴
- ✅ Best-effort：某步失败不影响后续部署
- ❌ 不要用 `sed` 改文件 | 不要用 `echo` 写多行文件 | 不要用 `cat` 读文件

---

## 目录

1. [前置条件](#1-前置条件)
2. [SOUL.md — Agent 人格层](#2-soulmd--agent-人格层)
3. [Holographic 记忆插件配置](#3-holographic-记忆插件配置)
4. [FTS5 中文分词补丁（必做）](#4-fts5-中文分词补丁必做)
5. [构建记忆系统：DIKW 四层模型](#5-构建记忆系统dikw-四层模型)
6. [三层自愈闭环（核心）](#6-三层自愈闭环核心)
7. [配置工具集](#7-配置工具集)
8. [Cron 定时任务](#8-cron-定时任务)
9. [部署后验证清单](#9-部署后验证清单)
10. [升级维护流程](#10-升级维护流程)
11. [常见问题](#11-常见问题)

---

## 1. 前置条件

```bash
# 检查环境
hermes version            # v0.10+
python3 --version         # 3.10+
python3 -c "import sqlite3; print('OK')"  # 必须 OK

# numpy（强烈推荐，否则 HRR 降级）
python3 -c "import numpy; print('OK')" || pip install numpy
```

**numpy 装不上怎么办？**
```bash
source ~/.hermes/hermes-agent/.venv/bin/activate
pip install numpy
```
无 numpy 时 HRR 降级为纯 FTS5+Jaccard，检索能力下降约 30%。

---

## 2. SOUL.md — Agent 人格层

### 2.1 文件位置

```
下载模板文件 → 改名 → 部署
  hermes-holographic-soul-完善版.md  →  ~/.hermes/SOUL.md
```

⚠️ **不能保留模板文件名**，必须改为 `SOUL.md`，否则 Agent 找不到。

### 2.2 SOUL 必须包含的 6 个模块

| 模块 | 作用 | 是否可压缩 |
|------|------|-----------|
| 三层人格框架 | 模型层/记忆层/Agent 层定义 | ❌ 不可删 |
| 思维协议 | 内部推理 + 中文 reasoning | ❌ 不可删 |
| 铁律表（8条） | P0-P8 行为准则 | ❌ 不可删 |
| Holographic 工具使用指南 | `fact_store` / `fact_feedback` 完整示例 | ❌ 不可删 |
| 会话初始化流程 | 新会话搜记忆 → 读文件 → 回复 | ✅ 可摘要 |
| DIKW 分流四问 | 分析完成后自动分流（含踩坑审查） | ✅ 可摘要 |

### 2.3 铁律表（参考）

| 优先级 | 规则 | 说明 |
|--------|------|------|
| **P0** | 破坏性操作先征得同意 | 改系统配置、重启服务、改 cron |
| **P1** | 记忆优先 | 新会话先查 Holographic，再读核心文件 |
| **P1.2** | 反馈闭环 | 新方法论自动 `fact_store` 写入 |
| **P1.3** | 事实校准 | 检索后自觉调 `fact_feedback` |
| **P2** | 精准表达 | 给结论、可运行命令 |
| **P3** | 反面审查 | 代码审查含边界/错误/对立场景 |
| **P4** | 书面记忆 | 重要决策后更新 MEMORY.md |
| **P4.1** | 容量管理 | MEMORY.md >85% 自动 DIKW 分流 |
| **P5** | 复用复盘 | 重复任务存为 skill |
| **P6** | 锚点守护 | 切换/压缩前写入 last_moment.md |
| **P7** | 工具上限 | 建议 ≤15 次/轮 |
| **P8** | 自动信任校准 | `fact_feedback_loop.py` cron 处理 |

### 2.4 query 关键词编码策略（最关键）

`fact_store` 的 `query` 参数决定了能不能搜到。使用**同义词包围策略**：

```json
// ✅ 好：覆盖各种说法
fact_store(query="建仓 买入 入场 加仓 进场 开仓 买进")

// ❌ 差：换个词就搜不到
fact_store(query="建仓")
```

分类编码模板：

| 类型 | 写法 |
|------|------|
| 投资原则 | `query="建仓 买入 入场 + 时机 等待 确认 + 保守 谨慎 观望"` |
| 用户偏好 | `query="报告 推送 通知 + 偏好 喜欢 习惯 方式"` |
| 系统配置 | `query="temperature 参数 配置 + MiniMax DeepSeek 模型"` |

---

## 3. Holographic 记忆插件配置

### 3.1 编辑 config.yaml

```yaml
plugins:
  memory_provider: holographic               # ← 关键：启用 Holographic

  hermes-memory-store:
    db_path: ~/.hermes/memory_store.db        # SQLite 数据库路径
    auto_extract: 'false'                     # 靠 SOUL DIKW 四问，不自提取
    default_trust: '0.5'                      # 新事实默认信任分
    min_trust_threshold: '0.3'                # 检索过滤下限
    temporal_decay_half_life: '0'             # 方法论不过期
    hrr_weight: 0.15                          # 中文场景推荐 0.15
```

### 3.2 参数说明

| 参数 | 默认值 | 推荐值 | 说明 |
|------|--------|--------|------|
| `hrr_weight` | 0.3 | **0.15** | 中文场景降 HRR 权重（噪声多），让 FTS5 精确匹配主导 |
| `default_trust` | 0.5 | 0.5 | 中性，长期通过反馈自然校准 |
| `min_trust_threshold` | 0.3 | 0.3 | 检索下限，太低召回噪声，太高漏掉 |
| `temporal_decay_half_life` | 0 | 0 | 方法论永久有效 |

### 3.3 重启 Gateway

```bash
systemctl --user restart hermes-gateway
# 或
kill $(pgrep -f 'hermes.*gateway')
hermes gateway run --replace
```

---

## 4. FTS5 中文分词补丁（必做）

**这是中文场景最关键的一步。** 不执行此步骤，所有中文检索结果 = 0 条。

### 4.1 为什么

FTS5 默认 `unicode61` tokenizer 不分割连续中文字符：
```
"分批建仓策略" → 整个做为一个 token ✅（英文正常）
                → 搜"建仓" 0 条 ❌（因为"分批建仓"是一个整体）
```

### 4.2 三步搞定

**Step 1：添加 `_space_cjk()` 函数**

编辑 `~/.hermes/hermes-agent/plugins/memory/holographic/store.py`，在 import 区后添加：

```python
import re

_CJK_PATTERN = re.compile(r'[\u4e00-\u9fff]')

def _space_cjk(text: str) -> str:
    """在 CJK 字符间插入空格，使 FTS5 能逐字分词"""
    if not _CJK_PATTERN.search(text):
        return text
    text = re.sub(r'([\u4e00-\u9fff])(?=[\u4e00-\u9fff])', r'\1 ', text)
    text = re.sub(r'([\u4e00-\u9fff])([^\u4e00-\u9fff\s])', r'\1 \2', text)
    text = re.sub(r'([^\u4e00-\u9fff\s])([\u4e00-\u9fff])', r'\1 \2', text)
    return text
```

> ▶️ **Agent 执行**：用 `patch` 写入 `_space_cjk` 函数。先找到 import 区末尾（`import time` 或最后一个 import 行），在其后插入：
> ```
> patch(path="~/.hermes/hermes-agent/plugins/memory/holographic/store.py",
>       old_string="import time",
>       new_string="import time\nimport re\n\n_CJK_PATTERN = re.compile(r'[\\u4e00-\\u9fff]')\n\ndef _space_cjk(text: str) -> str:\n    \"\"\"在 CJK 字符间插入空格，使 FTS5 能逐字分词\"\"\"\n    if not _CJK_PATTERN.search(text):\n        return text\n    text = re.sub(r'([\\u4e00-\\u9fff])(?=[\\u4e00-\\u9fff])', r'\\1 ', text)\n    text = re.sub(r'([\\u4e00-\\u9fff])([^\\u4e00-\\u9fff\\s])', r'\\1 \\2', text)\n    text = re.sub(r'([^\\u4e00-\\u9fff\\s])([\\u4e00-\\u9fff])', r'\\1 \\2', text)\n    return text\n")
> ```

**Step 2：修改写入路径（6 处）**

搜索 `store.py` 中所有 `INSERT INTO facts_fts`，对 content 过 `_space_cjk()`：

```python
# 改前
cursor.execute("INSERT INTO facts_fts (rowid, content) VALUES (?, ?)", (fact_id, content))

# 改后
fts_content = _space_cjk(content)
cursor.execute("INSERT INTO facts_fts (rowid, content) VALUES (?, ?)", (fact_id, fts_content))
```

同样修改搜索方法中的 query 解析，搜索时 query 也要空格化。

> ▶️ **Agent 执行**：对每个 `INSERT INTO facts_fts` 位置执行替换。以下是一处典型替换，其他 5 处类似：
> ```
> grep -n "INSERT INTO facts_fts" ~/.hermes/hermes-agent/plugins/memory/holographic/store.py
> # 对每一处，用 patch 把 `VALUES (?, ?, content_var)` 改为 `VALUES (?, ?, _space_cjk(content_var))`
> ```

**Step 3：重建 FTS5 索引**

```bash
cd ~/.hermes
# 停 gateway
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

conn = sqlite3.connect("memory_store.db")
conn.execute("DROP TABLE IF EXISTS facts_fts")
conn.execute("CREATE VIRTUAL TABLE facts_fts USING fts5(content, tags)")
for row_id, content, tags in conn.execute("SELECT rowid, content, tags FROM facts"):
    conn.execute("INSERT INTO facts_fts (rowid, content) VALUES (?, ?)",
                 (row_id, _space(content or "")))
conn.commit()
print("Done:", conn.execute("SELECT COUNT(*) FROM facts_fts").fetchone()[0], "rows")
conn.close()
PYEOF

# 重启 gateway
hermes gateway run --replace
```

> ▶️ **Agent 执行**：用 `terminal` 一次性执行以上 Step 3 的全部内容（从 `cd ~/.hermes` 到 `hermes gateway run --replace`），逐行执行。

### 4.3 验证

```bash
sqlite3 ~/.hermes/memory_store.db "SELECT COUNT(*) FROM facts_fts WHERE facts_fts MATCH '\"建 仓\"';"
```
预期 ≥3 条。

### 4.4 搜索时必须空格化

```bash
# ✓ 正确
fact_store(query="建 仓 策 略")

# ✗ 错误（搜不到）
fact_store(query="建仓策略")
```

---

## 5. 构建记忆系统：DIKW 四层模型

### 5.1 架构总览

```
┌─────────────────────────────────────────────┐
│         Hermes Agent 记忆系统                │
├──────────┬──────────────────────────────────┤
│ 🧠 大脑   │ Holographic（fact_store）         │
│           │ → 方法论、原则、红线               │
│           │ → 高频使用，跨 session 持久化      │
├──────────┼──────────────────────────────────┤
│ 📚 图书馆 │ vault/ + entities/               │
│           │ → 完整文档、结构化卡片             │
│           │ → 偶尔翻阅，read_file 访问        │
├──────────┼──────────────────────────────────┤
│ 📦 仓库   │ data/{模块}/cache/               │
│           │ → 动态数据、API 返回缓存           │
│           │ → 会变的、有时效的放这里           │
└──────────┴──────────────────────────────────┘
```

### 5.2 DIKW 分流四问（含踩坑审查）

每次分析完成后，强制自问：

| 问题 | 答案决定存哪 |
|------|-------------|
| 这个信息会变吗？ | **会变** → data cache / **不会变** → 大脑或图书馆 |
| 每次推理都要用吗？ | **高频** → 大脑（`fact_store`） / **偶尔查** → 图书馆（Vault） |
| 是一张卡片还是一本书？ | **卡片** → entities / **体系化** → vault |
| **是踩坑经验吗？** | **结论** → `fact_store(source="lesson")` / **完整经过** → `vault/踩坑记录/` |

### 5.3 "记住"类指令的 Skill

在 `SKILL.md` 中配置 triggers，当用户说"记住/存一下/保存"时自动触发 DIKW 分流：

```yaml
---
name: dikw-memory-flow
triggers: [记住, 存一下, 保存, 记一下, 归档, 复盘]
---
```

触发后 Agent 自动执行：归纳内容 → 四问分流（含踩坑审查）→ 选工具写入。

### 5.4 7+1 层检索与执行流水线

检索流水线定义在 SOUL.md 中，命中即返回。**第 7 层为执行层**，检索后决定用哪个工具处理。核心逻辑：**从不变→变、从本地→网络**。

```
第 0 层：指代词（"刚才/之前" → session_search）
第 1 层：大脑 — 方法论（Holographic fact_store 双重检索，含踩坑结论 source=lesson）
第 2 层：图书馆 — 踩坑经验（vault/踩坑记录/ — 完整经过）
第 3 层：图书馆 — 知识库（vault + entities）
第 4 层：图书馆 — 近期对话（session_search）
第 5 层：图书馆 — 缓存点（data/cache mtime + TTL，过期则更新）
第 6 层：图书馆 — 网络搜索（web_search）← 最后手段
 ↓
🛠 第 7 层（执行层）：工具调用决策 ← ⚠️
  扫描 skills → 选工具 → 查可用性 → 批量优先 → 安全验证
  → 执行/处理 → 结果/反馈 → 迭代方法论（存回大脑或图书馆）
```

---

## 6. 四层自愈闭环（核心）

从上一轮（2026-06-02）起，闭环已从三层扩展到四层。源码级 `_inject_vault_duty()` 作为第四层加入。

### 6.1 第一环：技能自动触发

**需要创建 1 个文件 + 修改 1 个文件。**

---

#### ▶️ 写文件：agent/skill_auto_trigger.py

完整源码：

```python
"""Skill auto-trigger: match user keywords → inject skill content."""
import os, hashlib, re, time

_TRIGGER_CACHE = {"skills": [], "mtime": 0, "skills_hash": ""}
SKILLS_BASE = os.path.expanduser("~/.hermes/skills")

def _walk_skills(base):
    result = []
    for root, dirs, files in os.walk(base):
        if "SKILL.md" not in files:
            continue
        path = os.path.join(root, "SKILL.md")
        with open(path, "r", errors="replace") as f:
            content = f.read()
        triggers = _extract_triggers(content)
        if triggers:
            result.append({"path": path, "triggers": triggers, "content": content})
    return result

def _extract_triggers(text):
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return []
    front = m.group(1)
    tm = re.search(r"triggers\s*:\s*\[([^\]]*)\]", front)
    if not tm:
        return []
    return [t.strip().strip('"').strip("'").lower() for t in tm.group(1).split(",")]

def _skills_hash(base):
    h = hashlib.md5()
    for root, dirs, files in os.walk(base):
        for f in files:
            if f == "SKILL.md":
                h.update(os.path.join(root, f).encode())
    return h.hexdigest()

def auto_load_triggered_skills(user_message: str) -> str | None:
    now = time.time()
    h = _skills_hash(SKILLS_BASE)
    cache = _TRIGGER_CACHE
    if not cache["skills"] or h != cache["skills_hash"] or (now - cache["mtime"]) > 300:
        cache["skills"] = _walk_skills(SKILLS_BASE)
        cache["skills_hash"] = h
        cache["mtime"] = now
    msg_lower = user_message.lower()
    for skill in cache["skills"]:
        for keyword in skill["triggers"]:
            if keyword in msg_lower:
                return skill["content"]
    return None

def clear_trigger_cache():
    _TRIGGER_CACHE["skills"] = []
```

> ▶️ **Agent 执行**：用 `write_file` 把以上全部源码写入 `~/.hermes/hermes-agent/agent/skill_auto_trigger.py`，保持缩进和引号不变。

---

#### ▶️ 打补丁：conversation_loop.py（+9 行）

在 `_should_review_memory` 判断之后、`user_msg` 构造之前插入自动触发钩子。

> ▶️ **Agent 执行**：用 `patch` 工具替换以下代码段：

```
patch(
  path="~/.hermes/hermes-agent/agent/conversation_loop.py",
  old_string="        if _should_review_memory:\n            self._inject_memory_review()\n        user_msg = ",
  new_string="        if _should_review_memory:\n            self._inject_memory_review()\n        # [auto-trigger] inject skill content by keyword match\n        try:\n            from agent.skill_auto_trigger import auto_load_triggered_skills\n            skill_content = auto_load_triggered_skills(user_message)\n            if skill_content:\n                user_message = skill_content + \"\\n\\n---\\n\\n\" + user_message\n        except Exception:\n            pass\n        user_msg = "
)
```

> ▶️ **验证**：
> ```bash
> python3 -c "import ast; ast.parse(open('$HOME/.hermes/hermes-agent/agent/conversation_loop.py').read()); print('Syntax OK')"
> ```

**SKILL.md triggers 示例**：

```yaml
---
name: memory-capacity-management
triggers: [整理记忆, memory满, 容量管理, 收拾记忆, 清理记忆, MEMORY满了, 记忆满了, 记忆快满了, 记忆整理]
---

name: fact-feedback-loop
triggers: [校准反馈, 反馈校准, fact_feedback, 信任校准, 信任分, 事实校准, memory_db, 清理事实]
---
```

> ▶️ **Agent 执行**：用 `write_file` 创建以下两个 SKILL.md 文件：

```yaml
# 文件1：~/.hermes/skills/system/memory-capacity-management/SKILL.md
---
name: memory-capacity-management
triggers: [整理记忆, memory满, 容量管理, 收拾记忆, 清理记忆, MEMORY满了, 记忆满了, 记忆快满了, 记忆整理]
---
# MEMORY.md 容量管理 — DIKW 自动分流
# 自动流程见第 6.2 节
# cron: check-core-capacity 每日 9:00 no_agent
```

```yaml
# 文件2：~/.hermes/skills/system/fact-feedback-loop/SKILL.md
---
name: fact-feedback-loop
triggers: [校准反馈, 反馈校准, fact_feedback, 信任校准, 信任分, 事实校准, memory_db, 清理事实]
---
# 信任分自动校准
# 自动流程见第 6.3 节
# cron: fact-feedback-calibrate 每周六 11:00
```

> 确保目录存在：
> ```bash
> mkdir -p ~/.hermes/skills/system/memory-capacity-management
> mkdir -p ~/.hermes/skills/system/fact-feedback-loop
> ```

### 6.2 第二环：MEMORY.md 容量管理

**问题**：MEMORY.md 有字符上限（~6000字）。>85% 时新增无法写入、挤占推理空间。

**自动分流流程**：

```
MEMORY.md/USER.md >85% → cron 触发（每日 9:00 no_agent 检测）
  ├─ 逐条读 MEMORY.md
  ├─ DIKW 四问
  │    会变吗？→ data cache
  │    高频用？→ fact_store（大脑）
  │    卡片 vs 书？→ entities / vault
  │    踩坑经验？→ 结论进 fact_store(source="lesson")，经过进 vault/踩坑记录/
  └─ 替换为一行索引
     [分类-关键词] | 一句话 + 详见路径
```

**索引行格式**：

```markdown
- [投资-调仓决策20260602] | 方案A：减013309 10%→17.5%，加001632 2.5%→5% | 详见 vault/...
- [系统-temperature机制] | MiniMax temperature 已从代码删除 | 详见 vault/...
```

**分流规则**：

| 信息类型 | 存哪 | 目标 | 格式 |
|---------|------|------|------|
| 用户偏好/原则 | 🧠 大脑 | `fact_store` | 短句 ≤50 字 |
| 方法论/工作流 | 🧠 大脑 | `fact_store` | 短句 + 关键词群 |
| 项目详情 | 📚 图书馆 | `vault/` | 完整文档 |
| 实体信息 | 🗂️ 卡片柜 | `entities/` | 结构化卡片 |
| 临时数据 | 📦 仓库 | `data/{模块}/cache/` | 带时间戳 |
| 过期信息 | 🗑️ 删除 | `memory remove` | — |

### 6.3 第三环：信任分自动校准

**问题**：Agent 经常忘记手动调 `fact_feedback`，大量事实长期无人校准。

**方案**：`agent/fact_feedback_loop.py` 直接操作 SQLite，用统计规则自动校准。

```python
"""Fact feedback loop — automated trust calibration."""
import sqlite3, os, datetime

DB_PATH = os.path.expanduser("~/.hermes/memory_store.db")

def calibrate(dry_run=True):
    conn = sqlite3.connect(DB_PATH)
    stats = {"downgrade": 0, "upgrade": 0, "decay": 0}
    now = datetime.datetime.now()
    
    rows = conn.execute(
        "SELECT fact_id, trust_score, retrieval_count, helpful_count, created_at "
        "FROM facts WHERE trust_score IS NOT NULL"
    ).fetchall()
    
    for fid, trust, rc, hc, ca in rows:
        # 规则1：检索≥3次但从未帮助 → 降权
        if rc >= 3 and hc == 0:
            new_trust = max(0.05, trust - 0.1)
            if not dry_run:
                conn.execute("UPDATE facts SET trust_score=? WHERE fact_id=?", (new_trust, fid))
            stats["downgrade"] += 1
        
        # 规则2：帮助比 >30% → 升权
        if rc > 0 and (hc / rc) > 0.3:
            new_trust = min(0.95, trust + 0.05)
            if not dry_run:
                conn.execute("UPDATE facts SET trust_score=? WHERE fact_id=?", (new_trust, fid))
            stats["upgrade"] += 1
        
        # 规则3：创建>14天且零检索 → 衰减
        age = (now - datetime.datetime.fromisoformat(ca)).days if ca else 999
        if age > 14 and rc == 0:
            new_trust = max(0.05, trust * 0.95)
            if not dry_run:
                conn.execute("UPDATE facts SET trust_score=? WHERE fact_id=?", (new_trust, fid))
            stats["decay"] += 1
    
    if not dry_run:
        conn.commit()
    conn.close()
    return stats
```

（完整版 344 行，含 `--report`、`--calibrate --apply` 参数解析和统计报告生成。此处展示核心逻辑，完整源码从配套包中获取。）

> ▶️ **Agent 执行**：从 `hermes-holographic-v3.tar.gz` 包中获取完整 `agent/fact_feedback_loop.py`，用 `write_file` 写入 `~/.hermes/hermes-agent/agent/fact_feedback_loop.py`。

**首次部署运行**：

```bash
python3 -m agent.fact_feedback_loop --calibrate --apply
```

```bash
# 查看健康报告
python3 -m agent.fact_feedback_loop --report

# 试运行（不写入）
python3 -m agent.fact_feedback_loop --calibrate

# 实际校准
python3 -m agent.fact_feedback_loop --calibrate --apply
```

**手动 vs 自动**：

| 维度 | 手动 `fact_feedback` | 自动 `fact_feedback_loop.py` |
|------|---------------------|---------------------------|
| 触发 | Agent 自觉 | cron 每周六 11:00 |
| 判断 | 语义准确性 | 统计规则（次数+帮助比+时效） |
| 范围 | 单条 | 全库批量 |
| 性价比 | Agent 判断上界 | 系统维护下界 |

---

## 7. 配置工具集

### 7.1 图片理解 — GLM-4V-Flash

在 `config.yaml` 中添加：

```yaml
models:
  vision:
    provider: custom
    model: glm-4v-flash
```

特点：费用低（约 0.01 元/次）、响应快（2-3 秒）、中文理解好。

### 7.2 Web Search — Tavily MCP

采用 adapter 架构，避免 MCP 负载均衡器的兼容问题：

```yaml
tools:
  web_search:
    backend: tavily
    endpoint: http://localhost:9999  # tavily-mcp-adapter
```

适配器脚本在 `~/.hermes/tavily-mcp-adapter.py`，监听 0.0.0.0:9999，自动转发到远程 MCP 负载均衡器。

`~/.hermes/.env` 中配置：
```
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx
```

验证：
```bash
curl http://localhost:9999/health
# 返回 {"status":"ok","adapter":"tavily-mcp"}
```

### 7.3 飞书消息 — Card 渲染

不要在 SOUL.md 中硬编码消息格式。使用飞书 Card JSON 2.0（`interactive` 类型），支持：

- Markdown 渲染（粗体、代码块、链接）
- 表格（通过 `column_set` + `column` 实现）
- 按钮操作

SOUL.md 中只需写：**飞书支持 Markdown 渲染，直接使用即可。** 底层渲染由 `feishu.py` 的 `_build_markdown_card_payload()` 处理。

### 7.4 上下文压缩模型

```yaml
compression:
  model: deepseek-ai/DeepSeek-V4-Flash
  threshold: 0.35  # 上下文利用率 >35% 时触发压缩
```

**注意**：压缩模型的上下文窗口不能太小。SiliconFlow 的某些小模型窗口仅 2K-4K，压缩长会话时会截断，导致上下文分裂、失忆。

---

## 8. Cron 定时任务

| 任务 | 调度 | 作用 | 对应 skill |
|------|------|------|-----------|
| 容量管理 | 每日 9:00 (no_agent) | 4核心文件 >85% 自动 DIKW 分流 | `memory-capacity-management` |
| 信任校准 | 每周六 11:00 | 信任分自动校准 | `fact-feedback-loop` |

> ▶️ **Agent 执行**：用 `cronjob` 工具创建以下两个定时任务：

```python
cronjob(action='create', name='check-memory-capacity',
        schedule='0 10 * * 5',
        prompt='检查 MEMORY.md 容量，>85% 时自动执行 DIKW 分流清理',
        skills=['memory-capacity-management'])

cronjob(action='create', name='fact-feedback-calibrate',
        schedule='0 11 * * 6',
        prompt='执行 Holographic 信任分校准：dry-run → 评估 → apply → 推送报告',
        skills=['fact-feedback-loop'])
```

> ▶️ **验证**：`cronjob(action='list')` 确认两个任务已注册。

---

## 9. 部署后验证清单

逐项确认，缺一不可：

```
□  fact_store 能存能搜（中文 ≥3 条命中）
□  fact_feedback 能正常校准
□  vision 图片理解正常（GLM-4V-Flash）
□  web search 返回有效结果
□  飞书消息 markdown 渲染正常
□  skill_auto_trigger 运行（说"整理记忆"自动触发）
□  cron 已注册（cronjob action='list'）
□  MEMORY.md 容量正常（<70%）
□  FTS5 中文搜索正常（sqlite3 直接查）
□  conversation_loop.py 9 行补丁已打
```

---

## 10. 升级维护流程

**不要直接 `git pull`**——会覆盖中文补丁和自动触发系统。

```bash
# 1. 建分支固化本地修改
cd ~/.hermes/hermes-agent
git checkout -b patches/custom
git add -A && git commit -m "local patches: FTS5 CJK + auto-trigger + feedback loop"

# 2. 拉取上游
git fetch --tags
git merge v2026.X.X --no-commit --no-ff

# 3. 逐文件解决冲突（重点检查）
#    - plugins/memory/holographic/store.py（FTS5 中文补丁）
#    - agent/conversation_loop.py（9 行注入钩子）
#    - agent/skill_auto_trigger.py（新增文件）
#    - agent/fact_feedback_loop.py（新增文件）
#    - gateway/platforms/feishu.py（card 渲染）

# 4. 逐功能验证
#    见第 9 章验证清单

# 5. 提交并打 tag
git commit -m "merge v2026.X.X + reapply patches"
git tag custom-v2026.X.X
```

---

## 11. 常见问题

### Q：第一次启动中文搜不到？
A：正常。必须打 FTS5 中文补丁（第 4 章），否则所有中文检索结果 = 0。

### Q：技能自动触发不工作？
A：检查三点：① `agent/skill_auto_trigger.py` 在正确路径；② `conversation_loop.py` 已打 9 行补丁；③ SKILL.md 有 `triggers` 字段。

### Q：`fact_store` 搜出来都是 0.46-0.47 分？
A：正常。7000+ 条事实中 HRR 向量过载约 5 倍，所有 probe 得分集中。降低 `hrr_weight` 到 0.15 让 FTS5 主导。

### Q：numpy 装不上？
A：在 venv 中装：`source ~/.hermes/hermes-agent/.venv/bin/activate && pip install numpy`。实在装不上也能用（HRR 降级）。

### Q：MEMORY.md 满了怎么办？
A：说"整理记忆"→ 自动触发容量管理 skill → 按 DIKW 分流。或者等 cron 每日 9:00 自动检测。

### Q：升级会丢补丁吗？
A：会。所有未提交的修改在 `git pull/rebase` 时会被覆盖。必须按第 10 章的 patches 分支流程操作。

---

## 附录：推荐目录结构

```
~/.hermes/
├── SOUL.md                    人格定义
├── AGENTS.md                  目录规范
├── config.yaml                主配置
├── .env                       API Key（不入 git）
├── memories/
│   ├── MEMORY.md              索引版笔记（≤6000字）
│   ├── USER.md                用户画像
│   └── TODO.md                待办
├── skills/
│   └── system/
│       ├── memory-capacity-management/SKILL.md
│       ├── fact-feedback-loop/SKILL.md
│       └── dikw-memory-flow/SKILL.md
├── hermes-agent/
│   └── agent/
│       ├── skill_auto_trigger.py     ← 新增
│       ├── fact_feedback_loop.py     ← 新增
│       └── conversation_loop.py      ← 打过补丁
├── data/
│   ├── memory/                 last_moment.md（会话锚点）
|   └── knowledge/vault/        知识库（系统文档、投资分析、踩坑记录...）
├── memory_store.db             Holographic 记忆库（SQLite + FTS5）
├── tavily-mcp-adapter.py       网络搜索适配器
└── cron/                       Cron 输出
```
