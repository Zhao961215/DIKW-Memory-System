# 工作区规范（Holographic 版）

> 本文件定义**基础设施层**（目录/路径/禁止事项），是文件存放的权威参考。
> 记忆引擎：Holographic（SQLite + FTS5 + Jaccard + HRR 代数），**跨 session 全局共享**，零 Docker 依赖。
> 配合 SOUL.md（Agent 人格）+ 记忆系统指南（Holographic 版）使用。

---

## 系统目录 / 数据流向

| 数据类型 | 路径 | 职责 |
|---------|------|------|
| Agent 人格定义 | `~/.hermes/SOUL.md` | 铁律、思维协议、身份 |
| 目录规范（本文件） | `~/.hermes/AGENTS.md` | 基础设施层 |
| 用户画像 | `~/.hermes/USER.md` | 用户偏好、风格、决策习惯 |
| 核心记忆 | `~/.hermes/MEMORY.md` | 操作知识、红线、索引（上限 ~6000 字符） |
| 待办事项 | `~/.hermes/TODO.md` | 唯一真实源 |
| 会话锚点 | `~/.hermes/data/memory/last_moment.md` | 上下文压缩/切换前写入，下个 Agent 自动读取 |
| 业务数据 | `~/.hermes/data/` | 按领域划分的子目录 |
| 知识库 | `~/.hermes/data/knowledge/vault/` | 体系化文档、实体页、笔记 |
| 记忆引擎 | `~/.hermes/memory_store.db` | Holographic SQLite 数据库（全局共享） |
| 技能库 | `~/.hermes/skills/` | 内置 + 自建 skill |
| 用户工具 | `~/.hermes/tools/` | 自定义脚本工具 |
| 系统文档 | `~/.hermes/docs/` | 部署配置文档 |
| Cron 脚本 | `~/.hermes/scripts/` | 系统硬编码 |
| 定时任务输出 | `~/.hermes/cron/` | 自动化产出 |
| 系统日志 | `~/.hermes/logs/` | 运行日志 |
| 会话历史 | `~/.hermes/sessions/` | 系统管理 |
| 临时文件 | `/tmp/hermes-*` | 7天清理 |
|| 系统代码 | `~/.hermes/hermes-agent/` | **严禁存放用户数据**；技能自动触发 `agent/skill_auto_trigger.py` + 信任自动校准 `agent/fact_feedback_loop.py` + vault-write 强制提炼 `agent/tool_executor.py._inject_vault_duty()` 在此 |
|| 系统 Cron 技能 | `~/.hermes/skills/system/` | 自愈闭环技能：memory-capacity-management + fact-feedback-loop |

**治理规则**：写入前查上表确认路径；不在 `~/.hermes/` 之外创建用户数据目录；路径不确定时用 `/tmp/hermes-*`，事后告知用户。

---

## 完整目录树

```
~/.hermes/
├── SOUL.md             人格定义（Agent 层）
├── AGENTS.md           目录规范（本文件）
├── MEMORY.md           核心记忆（~6000 chars，高频事实）
├── USER.md             用户画像（~3000 chars）
├── TODO.md             待办事项
├── data/               业务数据（按领域划分）
│   ├── memory/        last_moment.md（会话锚点）[注：-detail.md 已废弃，DIKW 分流由 Holographic 替代]
│   ├── knowledge/      知识库
│   │   └── vault/      体系化文档
│   │       ├── entities/  实体页
│   │       ├── 踩坑记录/  踩坑经验完整经过  ⭐
│   │       └── 分类/      文档
│   └── {业务模块}/      按领域（investment/ 等）
│       └── cache/       模块级缓存
├── memory_store.db     Holographic 记忆数据库（SQLite + FTS5，全局共享）
├── docs/               系统文档
├── skills/             技能库（内置 + 自建）
│   └── 分类/           技能按领域分类
├── tools/              用户工具
├── scripts/            Cron 预检脚本
├── cron/               定时任务配置与输出
├── cache/              Hermes 临时缓存（7天自动清理）
├── logs/               系统日志
├── sessions/           会话历史
├── config.yaml         主配置
└── hermes-agent/       系统代码 [严禁存放用户数据]
    └── agent/
        ├── skill_auto_trigger.py  技能自动触发（源码层）
        ├── fact_feedback_loop.py  信任分自动校准（源码层）
        └── tool_executor.py       内含 _inject_vault_duty() vault-write 强制提炼（源码级）
```

### Data 目录详解（按领域）

```
data/
├── memory/                会话锚点（last_moment.md，压缩/切换时写入）
│                           [注：-detail.md 已废弃，不再维护]
├── knowledge/             知识库
│   └── vault/             体系化文档
│       ├── entities/      实体页（基金/指数/行业/配置）
│       ├── 踩坑记录/      踩坑经验完整经过 ⭐
│       └── 00-系统文档/    系统类文档
│       └── 02-投资研究/    投资分析文档
│       └── ...            其他分类
├── investment/            投资业务
│   └── {模块}/            每个模块独立目录
│       ├── cache/         模块级缓存文件
│       ├── output/        模块产出
│       └── ...            模块特有目录
└── ...                    其他业务领域
```

---

## 缓存目录规范

Data Cache 是 DIKW 模型中的 D（Data）和 I（Information）层，存放会变的动态数据。

| 缓存类型 | 路径模式 | 默认有效期 | 说明 |
|---------|---------|-----------|------|
| 模块缓存 | `data/{模块}/cache/` | 数小时至30天 | 每个模块自己的缓存 |
| 全局缓存 | `cache/` | 7天 |  Hermes 自动清理 |

**核心规则**：
1. 每个模块有自己的 `cache/` 子目录，互不干扰
2. 写缓存时检查是否需要先建目录（`mkdir -p`）
3. 读缓存时检查 mtime（文件修改时间）+ 数据类型有效期
4. 不要在 `data/` 之外创建缓存目录

---

## 核心文件容量约束

核心文件（SOUL / MEMORY / USER / AGENTS）是每轮注入到 system prompt 中的内容，有字符上限。DIKW 分流清理策略：

| 文件 | 容量限制 | 策略 |
|------|---------|------|
| `SOUL.md` | ~20,000 字符 | 充足，铁律/协议精简为索引+全文 |
| `MEMORY.md` | ~6,000 字符 | 原则前置 + 索引行；详细内容走 vault/entities/fact_store |
| `USER.md` | ~3,000 字符 | 核心画像；补充偏好走 fact_store(user_pref) |
| `AGENTS.md` | ~5,000 字符（经验上限） | 目录规范本身 |

> **核心原则**：主文件存「核心版」——需要每轮直接可用的内容。完整版通过 Holographic（fact_store）+ vault + entities 分层存储。
> **容量管理**：每日 9:00 cron 自动检测，占用 >85% 时触发 DIKW 分流（方法论→fact_store，文档→vault，卡片→entities，动态→data/cache，主文件保留索引行）。

---

## 禁止事项

- ❌ 不在 `hermes-agent/` 下存放任何用户数据
- ❌ 不在 `~/.hermes/` 之外创建用户数据目录
- ❌ 不创建未列入本规范的顶层目录
- ❌ 业务数据不放 `data/` 以外的目录
- ❌ 日志不放 `logs/` 以外的目录
- ❌ 路径不确定时，优先用 `/tmp/hermes-*`，事后告知用户
- ❌ 不手动修改 `memory_store.db`（通过 `fact_store` / `fact_feedback` 工具操作）
  - ✅ 例外：`agent/fact_feedback_loop.py` 是系统信任分校准模块，可直接操作 SQLite，由 cron 触发
- ❌ 不在 `data/` 顶层直接放文件（必须按模块划分子目录）

---

## 豁免条款

系统稳定性 > 路径规范。以下情况可暂不受约束，事后告知用户：
- 系统自动生成的状态文件（gateway.pid/state.db）
- 第三方工具自动创建的目录
- Cron 系统硬编码路径（scripts/）
- Hermes 升级时自动创建的兼容目录

---

## 架构变更规则

目录架构锁定，任何增/删/改必须先征得用户同意。
