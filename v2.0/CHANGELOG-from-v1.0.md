# CHANGELOG: v1.0 → v2.0

> **发布日期**：2026-06-03
> **升级类型**：信息流 v2 升级（代码层 + 文档层）

## 🆕 新增（Added）

- **信息流 v2 升级**：`agent/information_flow/impl_v2.py` 成为默认实现
  - L1 大脑：FTS5 + Jaccard + HRR 三重混合评分（默认权重 0.4 / 0.3 / 0.3）
  - CJK 2-gram 滑窗分词（解决 FTS5 unicode61 不分割连续汉字）
  - retrieval_count 字段递增（修复 99.8% 冷数据假象）
  - L2-L4 ThreadPoolExecutor 并行执行
  - L4 trigram FTS5 中文兜底
  - L6 Tavily HTTP 直连（替换原占位实现）
- **健康检查 cron**（`f077b3d49af6` 每周日 10:00）：自动评估检索率/冷数据比/trust 分布

## 🔄 变更（Changed）

- `agent/information_flow/impl_v2.py` 成为默认实现（之前是 `v1`）
- `dict_to_v1.py` 文档结构：增加「v2 升级」章节
- 49K 完善版指南替换 25K 早期版（章节结构不变，内容大幅扩展）

## 🐛 修复（Fixed）

- FTS5 中文长句检索返回空（unicode61 不分割 CJK）→ 2-gram 兜底
- retrieval_count 不递增导致健康检查误报 → 每次 L1 命中后 UPDATE
- L2-L4 串行执行慢 → ThreadPoolExecutor 并行

## ❌ 移除（Removed）

- `agent/information_flow/impl_v1.py` 仍保留，但不再默认加载

## 📊 性能数据

| 指标 | v1.0 | v2.0 |
|------|------|------|
| 中文长句检索 | 0% 命中 | 100% 命中（6/6 测试） |
| 冷数据比 | 99.8% 假象 | 真实统计 |
| L2-L4 串行耗时 | T+3T+3T=7T | max(T)=T（并行） |

## 🔗 升级指南

从 v1.0 升级到 v2.0：

```bash
# 1. 备份当前信息流模块
cp -r ~/.hermes/hermes-agent/agent/information_flow/ ~/.hermes/hermes-agent/agent/information_flow.bak.v1.0/

# 2. 部署 v2 实现
cp agent/information_flow/impl_v2.py ~/.hermes/hermes-agent/agent/information_flow/

# 3. 重启 Gateway
hermes restart

# 4. 验证中文检索
python3 -c "from agent.information_flow import RetrievalPipeline; p = RetrievalPipeline.create('v2'); print('✅ v2 ready')"
```

## 📚 相关文档

- 完整 v2.0 指南：`记忆系统使用指南-完善版-v2.0.md`
- 源码层：`agent/information_flow/impl_v2.py`
- 部署指南：`docs/部署指南.md`
