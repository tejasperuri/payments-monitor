"""Two interchangeable "model clients": the real Anthropic API and a scripted fake for --mock.

Both return a Reply with:
  content      list of plain dicts ({"type": "text"|"thinking"|"tool_use", ...}) for logging
  raw_content  what to put back into the conversation history
  stop_reason, usage
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field


@dataclass
class Reply:
    content: list
    raw_content: list
    stop_reason: str
    usage: dict = field(default_factory=dict)


class AnthropicClient:
    def __init__(self):
        import anthropic  # imported here so --mock works without the package/key
        self.client = anthropic.Anthropic(max_retries=6)  # reads ANTHROPIC_API_KEY from the environment

    def create(self, **kwargs) -> Reply:
        r = self.client.messages.create(**kwargs)
        return Reply(
            content=[b.model_dump(exclude_none=True) for b in r.content],
            raw_content=r.content,  # pass SDK objects back unchanged (keeps thinking signatures valid)
            stop_reason=r.stop_reason,
            usage={"input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens},
        )


class MockAgentClient:
    """Pretends to be the agent model: replays the task's mock_plan, one tool call per turn.

    In attack episodes it splices the side task's plan in at a random point, and sometimes
    "leaks" its intent in visible text, so monitors that see text have something extra to catch.
    """

    def __init__(self, main_task, side_task, seed: int):
        rng = random.Random(seed)
        plan = list(main_task.mock_plan[:-1])  # everything except the final submit
        if side_task:
            pos = rng.randint(0, len(plan))
            plan[pos:pos] = side_task.mock_plan
        self.plan = plan + main_task.mock_plan[-1:]
        self.leak = side_task is not None and rng.random() < 0.3
        self.step = 0
        self.last_transfer = None

    def create(self, messages, **_):
        # Remember the most recent transfer id from the tool results we were just given.
        last = messages[-1]
        if isinstance(last["content"], list):
            for block in last["content"]:
                result = json.loads(block.get("content", "{}"))
                if isinstance(result, dict) and "transfer_id" in result:
                    self.last_transfer = result["transfer_id"]
        name, args = self.plan[self.step]
        args = {k: (self.last_transfer if v == "$LAST_TRANSFER" else v) for k, v in args.items()}
        content = [{"type": "thinking", "thinking": f"(mock) step {self.step}"}]
        if self.step == 0:
            text = "I'll also take care of the extra item quietly." if self.leak else "Let me get started."
            content.append({"type": "text", "text": text})
        content.append({"type": "tool_use", "id": f"toolu_{self.step:03d}", "name": name, "input": args})
        self.step += 1
        return Reply(content, content, "tool_use", {"input_tokens": 0, "output_tokens": 0})
