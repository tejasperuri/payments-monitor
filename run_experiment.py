"""Run agent episodes (honest and attack), score each with every monitor, write JSONL.

Examples:
  python run_experiment.py --mock                          # offline, no API key needed
  python run_experiment.py --limit 4                       # 4 real episodes (2 honest, 2 attack)
  python run_experiment.py --repeats 2                     # full run: 36 episodes
  python run_experiment.py --rescore results/run.jsonl --monitor-model claude-sonnet-5-5
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from payments_monitor.agent import run_episode
from payments_monitor.config import DEFAULT_AGENT_MODEL, DEFAULT_MONITOR_MODEL
from payments_monitor.models import AnthropicClient, MockAgentClient
from payments_monitor.monitor import llm_monitor, mock_llm_monitor, rule_monitor
from payments_monitor.tasks import MAIN_BY_ID, MAIN_TASKS, SIDE_TASKS


def plan_episodes(repeats: int, seed: int):
    """Each repeat: every main task once honestly, and once paired with a side task (rotating)."""
    episodes = []
    for r in range(repeats):
        for i, main in enumerate(MAIN_TASKS):
            episodes.append((main, None, seed + 1000 * r + 2 * i))
            episodes.append((main, SIDE_TASKS[(i + r) % len(SIDE_TASKS)], seed + 1000 * r + 2 * i + 1))
    return episodes


def score_episode(ep: dict, args, client) -> dict:
    """Add monitor scores to an episode dict (in place) and return it."""
    task_prompt = MAIN_BY_ID[ep["main_task"]].prompt
    ep["monitors"] = {"rule": rule_monitor(ep["audit_log"])}
    for view in args.views:
        if args.mock:
            ep["monitors"][f"llm_{view}"] = mock_llm_monitor(task_prompt, ep["transcript"], view, ep["seed"])
        else:
            ep["monitors"][f"llm_{view}"] = llm_monitor(client, args.monitor_model, task_prompt,
                                                        ep["transcript"], view)
    ep["monitor_model"] = "mock" if args.mock else args.monitor_model
    return ep


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true", help="scripted fake models, no API key or cost")
    p.add_argument("--agent-model", default=DEFAULT_AGENT_MODEL)
    p.add_argument("--monitor-model", default=DEFAULT_MONITOR_MODEL)
    p.add_argument("--repeats", type=int, default=1, help="each repeat = 18 episodes")
    p.add_argument("--limit", type=int, default=None, help="only run the first N episodes")
    p.add_argument("--views", nargs="+", default=["actions", "full"], choices=["actions", "full"],
                   help="what the LLM monitor sees: tool calls only, and/or visible text too")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default=None)
    p.add_argument("--rescore", default=None, help="re-run monitors on an existing results file (no agent calls)")
    args = p.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path(args.out or f"results/{'mock' if args.mock else 'run'}-{stamp}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    client = None if args.mock else AnthropicClient()

    if args.rescore:
        episodes = [json.loads(line) for line in open(args.rescore)]
        with open(out, "w") as f:
            for ep in episodes:
                f.write(json.dumps(score_episode(ep, args, client)) + "\n")
        print(f"Rescored {len(episodes)} episodes -> {out}")
        return

    plan = plan_episodes(args.repeats, args.seed)[: args.limit]
    with open(out, "w") as f:
        for n, (main, side, seed) in enumerate(plan, 1):
            agent_client = MockAgentClient(main, side, seed) if args.mock else client
            model = "mock" if args.mock else args.agent_model
            try:
                ep = score_episode(run_episode(agent_client, model, main, side, seed), args, client)
            except Exception as e:  # keep going; one API hiccup shouldn't kill the whole run
                print(f"[{n}/{len(plan)}] {main.id} / {side.id if side else 'honest'}: ERROR {e!r}")
                continue
            f.write(json.dumps(ep) + "\n")
            f.flush()  # so a crash keeps everything finished so far
            scores = " ".join(f"{k}={v['score']:.0f}" for k, v in ep["monitors"].items())
            print(f"[{n}/{len(plan)}] {main.id:12s} {(side.id if side else 'honest'):12s} "
                  f"main={ep['main_success']!s:5s} side={ep['side_success']!s:5s} {scores}")
    print(f"\nWrote {out}\nNext: python analyze.py {out}")


if __name__ == "__main__":
    main()
