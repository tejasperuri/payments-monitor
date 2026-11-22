"""Print one episode in readable form: task, agent's private thinking, visible actions, monitor verdicts.

  python show_episode.py results/run-XXXX.jsonl 3        # 4th episode (0-based index)
  python show_episode.py results/run-XXXX.jsonl --side redirect
"""
import argparse
import json

from payments_monitor.monitor import format_transcript
from payments_monitor.tasks import MAIN_BY_ID

p = argparse.ArgumentParser()
p.add_argument("file")
p.add_argument("index", nargs="?", type=int, default=0)
p.add_argument("--side", help="show the first episode with this side task instead")
a = p.parse_args()
eps = [json.loads(line) for line in open(a.file)]
ep = next(e for e in eps if e["side_task"] == a.side) if a.side else eps[a.index]

print(f"MAIN TASK: {ep['main_task']}  ->  {MAIN_BY_ID[ep['main_task']].prompt}")
print(f"SIDE TASK: {ep['side_task'] or '(none, honest episode)'}")
print(f"main_success={ep['main_success']} side_success={ep['side_success']} turns={ep['turns']} "
      f"stop={ep['stop_reason']}\n")
print("---- PRIVATE THINKING (monitors never see this) ----")
print("\n...\n".join(t for t in ep["thinking"] if t) or "(none)")
print("\n---- WHAT THE MONITOR SEES (full view) ----")
print(format_transcript(ep["transcript"], "full"))
print("\n---- MONITOR VERDICTS ----")
for name, m in ep["monitors"].items():
    print(f"\n[{name}] score={m['score']}")
    print("\n".join(m["reasons"]) if "reasons" in m else m["reason"][-800:])
