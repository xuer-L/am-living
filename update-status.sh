#!/bin/bash
# am-living 状态页数据生成脚本
# 由系统 crontab 每 10 分钟调用

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 加载配置
if [ ! -f config.env ]; then
    echo "ERROR: config.env not found. Copy config.env.example to config.env"
    exit 1
fi
source config.env

if [ -z "$GITHUB_TOKEN" ] || [ -z "$GITHUB_REPO" ]; then
    echo "ERROR: GITHUB_TOKEN and GITHUB_REPO must be set in config.env"
    exit 1
fi

DATA_DIR="${STATUS_DIR:-$SCRIPT_DIR}/data"
mkdir -p "$DATA_DIR"

# ── Agent 心跳（从 AGENT_1, AGENT_2, ... 动态解析）──
# 格式：key|名称|头像文件名|心跳文件路径
agents_json=$(python3 -c "
import json, os
from datetime import datetime, timezone, timedelta

agents = []
for k, v in sorted(os.environ.items()):
    if not k.startswith('AGENT_') or not v.strip():
        continue
    parts = v.split('|')
    if len(parts) < 2:
        continue
    key = parts[0].strip()
    name = parts[1].strip()
    avatar = parts[2].strip() if len(parts) > 2 else ''
    hb_file = parts[3].strip() if len(parts) > 3 else ''

    status = 'offline'
    ago = ''
    if hb_file and os.path.isfile(hb_file):
        try:
            with open(hb_file) as f:
                data = json.load(f)
            t = datetime.fromisoformat(data['ts'])
            mins = (datetime.now(timezone(timedelta(hours=8))) - t).total_seconds() / 60
            if mins < 5:
                status, ago = 'online', '< 5m ago'
            elif mins < 120:
                status, ago = 'idle', f'{mins:.0f}m ago'
            else:
                status, ago = 'offline', f'{mins:.0f}m ago'
        except:
            pass

    agent = {'name': name, 'status': status}
    if ago:
        agent['last_seen'] = ago
    if avatar:
        agent['avatar'] = avatar
    agents.append(agent)

print(json.dumps(agents, ensure_ascii=False))
")

# ── 待办任务 ──
tasks="[]"
if [ -n "$TODO_FILE" ] && [ -f "$TODO_FILE" ]; then
    tasks=$(python3 -c "
import re, json
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone(timedelta(hours=8)))
tasks = []
with open('$TODO_FILE') as f:
    for line in f:
        m = re.match(r'\|\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\|\s*(.+?)\s*\|\s*pending\s*\|', line)
        if m:
            t = datetime.fromisoformat(m.group(1).strip()).replace(tzinfo=timezone(timedelta(hours=8)))
            tasks.append({
                'time': m.group(1).strip(),
                'content': m.group(2).strip(),
                'is_today': t.date() == now.date()
            })
print(json.dumps(tasks, ensure_ascii=False))
" 2>/dev/null)
fi

# ── 活动状态 ──
activity="idle"
ACTIVITY_JSON="$DATA_DIR/activity.json"
history="[]"
if [ -f "$ACTIVITY_JSON" ]; then
    activity=$(python3 -c "import json; d=json.load(open('$ACTIVITY_JSON')); print(d.get('activity','idle'))" 2>/dev/null || echo "idle")
    history=$(python3 -c "import json; d=json.load(open('$ACTIVITY_JSON')); print(json.dumps(d.get('history',[]), ensure_ascii=False))" 2>/dev/null || echo "[]")
fi

# ── 评价 ──
comment=""
if [ -n "$COMMENT_FILE" ] && [ -f "$COMMENT_FILE" ]; then
    comment=$(head -1 "$COMMENT_FILE")
fi

# ── 组装 status.json ──
python3 -c "
import json, os

update_time = '$(date '+%Y-%m-%d %H:%M')'
agents = json.loads('''$agents_json''')

status = {
    'updated': update_time,
    'config': {
        'display_name': '${DISPLAY_NAME:-User}',
        'display_handle': '${DISPLAY_HANDLE:-@user}',
        'title': '${DISPLAY_NAME:-User} — Status',
        'footer': '${FOOTER_TEXT:-powered by am-living}',
        'comment_author': '${COMMENT_AUTHOR:-Agent}'
    },
    'user': {
        'activity': '''$activity''',
        'last_active': update_time
    },
    'agents': agents,
    'tasks': json.loads('''$tasks'''),
    'history': json.loads('''$history'''),
    'comment': '''$comment'''
}

with open('$DATA_DIR/status.json', 'w') as f:
    json.dump(status, f, ensure_ascii=False, indent=2)
print('JSON assembled')
"

# ── 推送到 GitHub ──
python3 << 'PYPUSH'
import json, base64, urllib.request, os, sys

TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPO", "")
DATA_DIR = os.environ.get("DATA_DIR", "data")
API = f"https://api.github.com/repos/{REPO}/contents"
FILE = "data/status.json"
LOCAL = os.path.join(DATA_DIR, "status.json")

with open(LOCAL, "rb") as f:
    content = base64.b64encode(f.read()).decode()

body = {"message": f"auto-update", "content": content}
try:
    req = urllib.request.Request(f"{API}/{FILE}", headers={"Authorization": f"token {TOKEN}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        sha = json.loads(resp.read()).get("sha", "")
    if sha:
        body["sha"] = sha
except:
    pass

data = json.dumps(body).encode()
req = urllib.request.Request(
    f"{API}/{FILE}", data=data,
    headers={"Authorization": f"token {TOKEN}", "Content-Type": "application/json"},
    method="PUT"
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    print(f"Pushed OK")
except Exception as e:
    print(f"Push failed: {e}", file=sys.stderr)
    sys.exit(1)
PYPUSH
