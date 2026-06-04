# MEMORY.md — 你的 Agent 笔记本

> ⚠️ 这是模板文件。部署后请按实际内容填充。
> MEMORY.md 是每轮注入 system prompt 的文件，容量有限（~6,000 chars），**只存高频使用的核心信息**。
> 详情走 Holographic（`fact_store`）或知识库（`vault/`）。

---

## 一、核心原则

- 这里写你最常用的事实
- 一行一条，短句最佳（≤ 50 字）
- 示例：净值数据升序排列，`iloc[-1]` 才是最新值

## 二、关键事实

### 系统配置
- Hermes HOME: `~/.hermes`
- 记忆引擎: Holographic (SQLite + FTS5 + HRR)
- DIKW 检索管道: v2（默认）

### 重要红线
- 你的操作限制、禁止事项
- 示例：禁止用 A 作为 B 的 fallback（会出荒谬结论）

---

## 三、待办事项

- [ ] 第一条待办
- [ ] 第二条待办

---

> **容量管理**：当占用 >85% 时触发 `memory-capacity-management` skill 自动 DIKW 分流。
> 创建时间：____年__月__日
