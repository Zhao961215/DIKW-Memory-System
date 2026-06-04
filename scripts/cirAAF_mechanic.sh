#!/usr/bin/env bash
# CIRAAF 机械引擎 — 每周健康报告生成器
# 用于 cron 的 no_agent=True 模式：执行并输出报告
# 输出格式：纯文本
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
AGENT_DIR="$HERMES_HOME/hermes-agent"
VENV_DIR="$AGENT_DIR/venv"
SCRIPT="$AGENT_DIR/agent/cirAAF_mechanic.py"

if [ ! -f "$SCRIPT" ]; then
    echo "❌ CIRAAF 机械引擎未找到: $SCRIPT"
    exit 1
fi

cd "$AGENT_DIR"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -d "$AGENT_DIR/.venv" ]; then
    source "$AGENT_DIR/.venv/bin/activate"
fi

# ── 生成报告 ──
echo "────────────────────────────────────────────"
echo "  🧠 CIRAAF 周健康报告 | $(date +%Y-%m-%d\ %H:%M)"
echo "────────────────────────────────────────────"
python3 -m agent.cirAAF_mechanic
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠️  CIRAAF 引擎异常退出 (exit=$EXIT_CODE)"
    exit $EXIT_CODE
fi

# 尝试衰减（三条件检查自动判断是否执行）
echo ""
echo "────────────────────────────────────────────"
echo "  ⚙️  机械衰减检查"
echo "────────────────────────────────────────────"
python3 -m agent.cirAAF_mechanic --decay

# 检查是否有领域健康分 < 60
HEALTH_INFO=$(python3 -c "
import json, sqlite3
from pathlib import Path
db=Path.home()/'.hermes'/'memory_store.db'
conn=sqlite3.connect(str(db))
conn.row_factory=sqlite3.Row
domains={'投资':['investment','project'],'系统':['system','tool'],'用户':['user_pref'],'开发':['project','decision','discovery'],'方法':['general','reflect']}
bad=[]
for name, cats in domains.items():
    ph=','.join('?' for _ in cats)
    cur=conn.execute(f'SELECT COUNT(*) as total,AVG(trust_score) as avg_trust FROM facts WHERE category IN ({ph})', cats)
    r=dict(cur.fetchone())
    avg=r['avg_trust'] or 0.5
    health=int(min(avg/0.8*40,40)+30+min(r['total']/200*30,30))
    if health<60:
        bad.append(f'{name}({health})')
conn.close()
if bad:
    print('NEEDS_ATTENTION:'+','.join(bad))
else:
    print('HEALTHY')
")

if echo "$HEALTH_INFO" | grep -q "NEEDS_ATTENTION"; then
    echo ""
    echo "⚠️  ⚠️  ⚠️  以下领域需要关注:"
    echo "  $(echo $HEALTH_INFO | cut -d: -f2 | tr ',' '\n  ')"
fi
