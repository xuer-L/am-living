#!/usr/bin/env python3
"""
每 30 分钟从最近 session 中提取用户活动摘要
支持 MiMo / DeepSeek API，写入 data/activity.json
"""
import json, os, sys, glob, re
from datetime import datetime, timezone, timedelta
import urllib.request

# ── 加载配置 ──
def load_env(path):
    env = {}
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
env = load_env(os.path.join(SCRIPT_DIR, "config.env"))

SESSIONS_DIR = env.get("SESSIONS_DIR", "")
OUTPUT = os.path.join(SCRIPT_DIR, "data", "activity.json")
LOOKBACK = int(env.get("LOOKBACK_HOURS", "6"))

# AI 配置（优先 MiMo，其次 DeepSeek）
MIMO_KEY = env.get("MIMO_KEY", "")
MIMO_MODEL = env.get("MIMO_MODEL", "mimo-v2.5-pro")
DEEPSEEK_KEY = env.get("DEEPSEEK_KEY", "")
DEEPSEEK_MODEL = env.get("DEEPSEEK_MODEL", "deepseek-chat")

TZ = timezone(timedelta(hours=8))
now = datetime.now(TZ)
cutoff = now - timedelta(hours=LOOKBACK)

SKIP = ["Subagent Context", "cron:", "heartbeat poll",
        "Conversation info (untrusted metadata)",
        "chat_id", "chat_type", "OpenClaw heartbeat"]


def get_recent_user_messages():
    if not SESSIONS_DIR or not os.path.isdir(SESSIONS_DIR):
        return []
    messages = []
    for f in glob.glob(os.path.join(SESSIONS_DIR, "*.jsonl")):
        if ".trajectory." in f or ".lock" in f or ".checkpoint." in f:
            continue
        if os.path.getmtime(f) < cutoff.timestamp():
            continue
        try:
            with open(f) as fh:
                for i, line in enumerate(fh):
                    if i > 5000:
                        break
                    try:
                        d = json.loads(line)
                        if d.get("type") != "message":
                            continue
                        msg = d.get("message", {})
                        if msg.get("role") != "user":
                            continue
                        ts_str = d.get("timestamp", "")
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(TZ)
                        if ts < cutoff:
                            continue
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            content = " ".join(
                                item.get("text", "") for item in content
                                if isinstance(item, dict) and item.get("type") == "text"
                            )
                        if not content or len(content) < 5:
                            continue
                        if any(s in content for s in SKIP):
                            continue
                        if content.strip().startswith("{") or content.strip().startswith("`"):
                            continue
                        content = re.sub(r'^\[\w{3}\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+GMT[+-]\d+\]\s*', '', content)
                        if len(content) < 3:
                            continue
                        messages.append(f"[{ts.strftime('%H:%M')}] {content[:150]}")
                    except:
                        continue
        except:
            continue
    return messages[-30:][::-1]


def call_api(prompt, model, api_url, api_key, max_tokens=2000):
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }).encode()

    req = urllib.request.Request(api_url, data=data, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    })

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"]
        # 检查 MiMo 推理模型返回空内容
        if not content.strip():
            reasoning = result["choices"][0]["message"].get("reasoning_content", "")
            print(f"Empty output, reasoning: {reasoning[:100]}", file=sys.stderr)
            return None
        return content


def summarize(texts):
    prompt = (
        "根据以下用户消息，生成活动摘要。\n"
        "这是用户的个人状态页，只描述用户在做什么。\n\n"
        "规则：\n"
        "- 每行一条：HH:MM 活动描述\n"
        "- 描述 15 字以内，省略主语\n"
        "- 按时间倒序，最多 8 条\n"
        "- 只输出摘要，无解释\n\n"
        f"用户消息：\n" + "\n".join(texts)
    )

    content = None

    # 优先 MiMo
    if MIMO_KEY:
        try:
            content = call_api(prompt, MIMO_MODEL,
                "https://token-plan-cn.xiaomimimo.com/v1/chat/completions", MIMO_KEY)
        except Exception as e:
            print(f"MiMo failed: {e}", file=sys.stderr)

    # 回退 DeepSeek
    if not content and DEEPSEEK_KEY:
        try:
            content = call_api(prompt, DEEPSEEK_MODEL,
                "https://api.deepseek.com/chat/completions", DEEPSEEK_KEY, max_tokens=500)
        except Exception as e:
            print(f"DeepSeek failed: {e}", file=sys.stderr)

    if not content:
        return None

    # 解析
    entries = []
    for line in content.strip().split("\n"):
        m = re.match(r'(\d{1,2}:\d{2})\s+(.+)', line.strip())
        if m:
            entries.append({"time": m.group(1), "text": m.group(2).strip()})
    return entries


def main():
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    texts = get_recent_user_messages()

    prev = None
    try:
        with open(OUTPUT) as f:
            prev = json.load(f)
    except:
        pass

    if not texts:
        if prev and prev.get("history"):
            result = {
                "updated": now.strftime("%Y-%m-%d %H:%M"),
                "activity": prev["activity"],
                "history": prev["history"]
            }
        else:
            result = {"updated": now.strftime("%Y-%m-%d %H:%M"), "activity": "idle", "history": []}
    else:
        summary = summarize(texts)
        if not summary and prev and prev.get("history"):
            summary = prev["history"]
        if not summary:
            summary = [{"time": now.strftime("%H:%M"), "text": "busy"}]
        result = {
            "updated": now.strftime("%Y-%m-%d %H:%M"),
            "activity": summary[0]["text"] if summary else "busy",
            "history": summary[:8]
        }

    with open(OUTPUT, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(result.get('history', []))} entries")


if __name__ == "__main__":
    main()
