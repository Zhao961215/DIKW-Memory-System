# CHANGELOG: v2.0 → v2.1

> **发布日期**：2026-06-03
> **升级类型**：CIRAAF 5-layer 自愈（领域级结构一致性 + 宏观重构）

## 🆕 新增（Added）

### 第⑤层 CIRAAF 宏观重构（核心升级）

| 组件 | 说明 |
|------|------|
| `agent/cirAAF_mechanic.py` | 三齿轮架构机械引擎（Gear 1 源码 + Gear 2 cron skill + Gear 3 源码） |
| `scripts/cirAAF_mechanic.sh` | cron 包装脚本 |
| `brain-periodic-refactor` skill | Gear 2 反射入口（每周日 10:00 no_agent 模式触发） |
| 5 大领域健康监控 | 投资 63 / 系统 62 / 用户 64 / 开发 60 / 方法 57 |
| 机械衰减机制 | DB >60 天激活；年龄守卫保护幼年数据；3 条件独立判断 |

### 集成改进

- 三层保养流水线：① 容量管理（自动）→ ② 信任校准（自动）→ ③ CIRAAF 反射（LLM 驱动）
- Gear 2 与已有 skill 配合：失败注入 → Gear 3 修复 → 标记 refactored → 下次 CIRAAF 增量检查
- 通用版文件同步：本地修改 → 同步 `cache/documents/hermes-holographic-*-完善版.md`（独立副本，需手动同步）

## 🔄 变更（Changed）

- 自愈闭环层级：4-layer → **5-layer**（新增 CIRAAF）
- `hermes-holographic-readme-完善版.md`：描述从「4-layer」改为「5-layer + CIRAAF」
- 仓库 description：「Pure SQLite memory system for Hermes Agent. Zero Docker, zero external services. **5-layer self-healing + CIRAAF**. 中文 FTS5 patches included.」

## 📊 健康指标

| 指标 | v2.0 | v2.1 |
|------|------|------|
| 自愈层数 | 4 | **5**（+CIRAAF 领域级）|
| 零 LLM 比例 | 50%（2/4）| **66%**（4/6 cron no_agent） |
| 领域覆盖 | 单 fact | **5 大领域**（投资/系统/用户/开发/方法）|
| 衰减机制 | 时间（cron）| **机械 + 年龄守卫** |

## 🐛 修复（Fixed）

- v2.0 的 4-layer 只处理单 fact 质量问题 → CIRAAF 补充领域级结构一致性问题
- 通用版文件与本地文件不一致风险 → README 同步策略明确化

## 📦 部署 CIRAAF

```bash
# 1. 复制机械引擎
cp agent/cirAAF_mechanic.py ~/.hermes/hermes-agent/agent/

# 2. 创建 cron 包装脚本
mkdir -p ~/.hermes/scripts
cp scripts/cirAAF_mechanic.sh ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/cirAAF_mechanic.sh

# 3. 注册 cron（每周日 10:00，no_agent 模式）
cronjob(action='create', name='cirAAF-mechanic',
        script='cirAAF_mechanic.sh',
        schedule='0 10 * * 0',
        no_agent=True)

# 4. 健康验证
python3 -m agent.cirAAF_mechanic --report
```

## 🔗 完整文档

- CIRAAF 完整源码：`CIRAAF-源码部署指导-v2.1.md`（29K，含 3.1 机械引擎 + 3.2 cron 脚本 + 3.3 Gear 2 skill）
- 完整 v2.1 指南：`记忆系统使用指南-完善版-v2.1.md`
- 顶层 README：`/README.md`
