import json, glob, os, sys, bisect
from datetime import datetime
from collections import defaultdict
BASE = os.path.expanduser("~/.claude/projects")
TASKS = "/Users/fabienboismoreau/Documents/Projects/Nextory/Nextory_ai/nextory/.factory/tasks"

def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()

def step_windows(tid):
    starts = []
    for l in open(f"{TASKS}/{tid}/events.jsonl"):
        e = json.loads(l)
        if e.get("type") == "step_started":
            starts.append((ts(e["ts"]), e["step"]))
    return starts

def step_at(starts, t):
    keys = [s[0] for s in starts]
    i = bisect.bisect_right(keys, t) - 1
    return starts[i][1] if i >= 0 else "(before)"

def scan(f, starts, agg, sub=False):
    first = None
    seen = set()
    for l in open(f):
        try: r = json.loads(l)
        except Exception: continue
        if "timestamp" not in r: continue
        t = ts(r["timestamp"])
        if first is None: first = t
        step = step_at(starts, first if sub else t)
        a = agg[step]
        m = r.get("message") or {}
        if not isinstance(m, dict): continue
        u = m.get("usage")
        mid = m.get("id") or r.get("requestId")
        if u and r.get("type") == "assistant" and mid not in seen:
            seen.add(mid)
            ctx = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            k = "sub_" if sub else ""
            a[k + "calls"] += 1
            a[k + "read"] += u.get("cache_read_input_tokens", 0)
            a[k + "write"] += u.get("cache_creation_input_tokens", 0) + u.get("input_tokens", 0)
            a[k + "out"] += u.get("output_tokens", 0)
            if not sub:
                a["ctx_min"] = min(a.get("ctx_min", 10**9), ctx)
                a["ctx_max"] = max(a.get("ctx_max", 0), ctx)
        c = m.get("content")
        if not sub and r.get("type") == "user" and isinstance(c, list):
            for x in c:
                if isinstance(x, dict) and x.get("type") == "tool_result":
                    cc = x.get("content")
                    n = len(json.dumps(cc)) if not isinstance(cc, str) else len(cc)
                    a["toolres_chars"] += n

def task_report(tid):
    t = json.load(open(f"{TASKS}/{tid}/task.json"))
    sid = t["session_id"]
    mains = glob.glob(f"{BASE}/*/{sid}.jsonl")
    if not mains: return None
    starts = step_windows(tid)
    agg = defaultdict(lambda: defaultdict(int))
    scan(mains[0], starts, agg)
    for s in glob.glob(f"{BASE}/*/{sid}/subagents/*.jsonl"):
        scan(s, starts, agg, sub=True)
    return t["pipeline"], agg

if __name__ == "__main__":
    total = defaultdict(lambda: defaultdict(int))
    for tid in sys.argv[1:]:
        res = task_report(tid)
        if not res: continue
        pipe, agg = res
        allread = sum(v["read"] + v["sub_read"] for v in agg.values())
        print(f"\n## {tid} ({pipe}) total reads {allread/1e6:.1f}M")
        print(f"{'step':28} {'calls':>5} {'readM':>6} {'%':>4} {'ctx start>end k':>16} {'toolres k chars':>15} {'sub calls':>9} {'sub readM':>9}")
        for step, v in sorted(agg.items(), key=lambda kv: -(kv[1]["read"] + kv[1]["sub_read"])):
            r = v["read"] + v["sub_read"]
            if r < 0.005 * allread: continue
            print(f"{step:28} {v['calls']:5} {v['read']/1e6:6.1f} {100*r/allread:4.0f} {v.get('ctx_min',0)//1000:>7}>{v.get('ctx_max',0)//1000:<7} {v['toolres_chars']//1000:15} {v['sub_calls']:9} {v['sub_read']/1e6:9.1f}")
