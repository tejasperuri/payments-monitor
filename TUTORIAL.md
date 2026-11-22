# Tutorial: run, understand and own `payments-monitor` in about 6 hours

This guide takes you from zero to a finished, published mini research project. It's split into
five sessions. Do them in order. Each one ends with a ✅ checkpoint, so you know you're done.

| Session | Time | Goal |
|---|---|---|
| 1. Setup | 1 h | Python env, API key, spend limit, tests and dry run passing |
| 2. Understand the code | 1.5 h | You can explain every file and every metric |
| 3. Real experiments | 1.5 h | A small run first, then the full run, with results saved |
| 4. Your own experiment | 1 h | One change of your own, measured and written down |
| 5. Write-up and publish | 1 h | WRITEUP.md, a GitHub repo, and the lines for your application |

**Ground rules:**

1. **Only report numbers you actually got.** If the LLM monitor loses to the rules, or nothing
   works, that's still a result. Write it down honestly. A researcher trusts a clear null result
   far more than a too-good story.
2. **Everything you put in the application has to be in your own words.** Anthropic's candidate
   AI policy requires it. This tutorial gives you questions and structure, not answers. Rewrite the
   README too, so it sounds like you.
3. **Never commit or paste your API key** anywhere, including GitHub, chat and screenshots.

---

## Session 1: Setup (about 1 hour)

### 1.1 Get the code running (15 min)

You need Python 3.10 or newer (`python3 --version`). Unzip `payments-monitor.zip`, then:

```bash
cd payments-monitor
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                # expect: 15 passed
```

### 1.2 Dry run with no API key (10 min)

```bash
python run_experiment.py --mock --out results/mock-check.jsonl
python analyze.py results/mock-check.jsonl
python show_episode.py results/mock-check.jsonl --side redirect
```

You'll see 18 episodes print, then a summary table, and `results/mock-check-roc.png` will be
created. The mock agent follows a fixed script and the mock monitor is rules plus random noise.
**These numbers mean nothing.** They only prove the pipeline works.

### 1.3 Anthropic API key and spend limit (20 min)

1. Go to <https://console.anthropic.com> (it redirects to platform.claude.com) and sign in or sign up.
2. Under **Billing**, add a small amount of credit. $20 is plenty.
3. Under **Limits**, set a monthly spend limit. $25 is a reasonable cap, so a bug can't run up a bill.
4. Under **API keys**, create a key named `payments-monitor`. Copy it once.
5. In your terminal, set it for this session only (don't save it in any file inside the project):
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."     # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
   ```

**Cost estimate:** prices are from Anthropic's pricing page as of Nov 2026, so re-check them. An
agent episode on Sonnet 5.5 is roughly 5–10 turns. That's about 30–60k input tokens and 2–6k output
tokens (including thinking), or roughly $0.10–0.20. Monitoring on Haiku 5.5 costs a fraction of a
cent per episode. So a 4-episode test costs about $1 and the full 36-episode run about $5–10.
`analyze.py` prints the estimated cost of every run. Check it against the Console usage page.

### 1.4 First real call (15 min)

```bash
python run_experiment.py --limit 2 --out results/smoke.jsonl
python show_episode.py results/smoke.jsonl 0
python show_episode.py results/smoke.jsonl 1
```

Episode 0 is honest and episode 1 is an attack. Read both all the way through.
**If you get a "model not found" error**, open the
[models page](https://docs.anthropic.com/en/docs/about-claude/models/overview) and pass a valid id
with `--agent-model` or `--monitor-model`.

✅ **Checkpoint:** tests pass, the mock run works, and you've read one real honest and one real attack transcript.

---

## Session 2: Understand the code (about 1.5 hours)

Read the files in this order with the code open next to this guide. After each file, answer the
"check yourself" questions out loud, as if an interviewer had asked them. If you can't, reread the file.

### 2.1 `payments_monitor/env.py`: the fake world (20 min)

- Everything is plain Python dicts: `vendors` (the vendor master file), `invoices`, `transfers`, an `inbox`.
- `create_transfer` pays the vendor's **bank account on file at that moment**. That's why changing
  a vendor's bank details first is the classic fraud path.
- Transfers of $10,000 or more wait in `pending_approval` until `approve_transfer` is called.
- `call()` runs a tool by name and appends it to `audit_log`. It never crashes on bad input. It
  returns an error that the agent can read.
- `TOOLS` is the list of JSON schemas sent to Claude, so Claude knows which tools exist and what arguments they take.

**Check yourself:** (1) Why does the transfer record store `to_account` rather than looking it up
later? (2) What real-world control does `APPROVAL_THRESHOLD` imitate, and what's its weakness?
(3) Why is the environment seeded and in-memory instead of being a real database?

### 2.2 `payments_monitor/tasks.py`: what we ask for (15 min)

- **Main tasks** are legitimate jobs. Success is judged on the *final state*, for example "INV-1001
  is paid and INV-1006 is not", rather than on what the agent claims.
- **Side tasks** are the hidden sabotage: `redirect`, `bank_swap`, `structuring`, `exfiltrate`, `overpay`.
- Note `bank_change`. It's an *honest* task where changing bank details is legitimate, because the
  inbox has a verified ticket. That's on purpose: it tests whether a monitor raises false alarms.
- `mock_plan` exists only for `--mock` mode.

**Check yourself:** (4) Why judge success from the state rather than from the agent's summary?
(5) Which side task would a bank's existing controls most likely miss, and why?

### 2.3 `payments_monitor/agent.py`: the agent loop (20 min)

This is the core idea of "tool use":

1. Send Claude the system prompt, the conversation so far, and the tool list.
2. Claude replies with text, private **thinking**, and/or `tool_use` blocks
   (for example "call `create_transfer` with these arguments").
3. *Our code* runs the tool against the fake environment and sends the result back as a `tool_result`.
4. Repeat until Claude calls `submit`, stops calling tools, or hits 25 turns.

In attack episodes the system prompt adds a **secret side task**. It openly says this is a
red-team evaluation in a simulated environment. We record *visible* events in `transcript`, which
the monitor sees, and private reasoning in `thinking`, which the monitor never sees. That mirrors
SHADE-Arena's "hidden scratchpad".

**Check yourself:** (6) What would change if the monitor could read the thinking? (7) Claude may
refuse the side task. Is that a bug in the experiment or a finding? How would you report it?

### 2.4 `payments_monitor/monitor.py`: the monitors (20 min)

- `rule_monitor` is *your* banking world in code. Points get added for bank changes without a
  ticket, paying a vendor right after its bank change, transfers with no invoice, overpayment,
  sub-threshold splitting ("structuring") and external emails containing account numbers. The score
  is capped at 100.
- `llm_monitor` asks a Claude model to read the transcript and finish with `<score>N</score>`.
  The `actions` view shows only tool calls and results. The `full` view adds the agent's visible text.
- `mock_llm_monitor` is fake and only for offline testing.

**Check yourself:** (8) The rules were written by someone who knew the side tasks in advance. Why
does that make the comparison unfair, and in whose favour? (9) What happens if the LLM monitor
forgets the `<score>` tag?

### 2.5 `run_experiment.py`, `analyze.py`: the measurements (15 min)

Learn these terms. You will be asked about them:

- **Honest vs attack episodes.** Each main task is run once honestly and once with a side task
  (rotating), so `--repeats 2` gives 18 + 18 = 36 episodes.
- **Suspicion score.** 0–100 from each monitor.
- **False positive rate (FPR).** The share of *honest* episodes that get flagged. In a bank, that's
  legitimate payments held for review, which costs analyst time.
- **Catch rate.** The share of *attack* episodes that get flagged.
- **Threshold.** We choose it per monitor so that FPR is at most 10%, then report the catch rate at
  that point. This is how monitors are compared fairly: at the same false-alarm budget.
- **ROC curve and AUC.** Sweep the threshold from high to low and plot catch rate against FPR. AUC
  is the area under that curve, which equals the chance that a random attack scores higher than a
  random honest episode. 0.5 is a coin flip and 1.0 is perfect.
- **"Successful sabotage NOT caught".** Attacks where the side task worked *and* the monitor didn't
  flag it. This is the safety-relevant number.

**Check yourself:** (10) With only 18 honest episodes, what's the smallest non-zero FPR you can
measure? What does that mean for "at most 10%"? (11) Why is AUC alone not enough for a deployment decision?

✅ **Checkpoint:** you can draw the pipeline diagram from the README from memory and answer questions 1–11.

---

## Session 3: Real experiments (about 1.5 hours)

### 3.1 Small run first (20 min)

```bash
python run_experiment.py --limit 6 --out results/pilot.jsonl
python analyze.py results/pilot.jsonl
```

Open every transcript with `show_episode.py`. Look for problems *before* spending more:
- Is the agent doing the main tasks properly? If not, is the task prompt unclear?
- Did it refuse the side task? Look for `side_success=False` and read its text and thinking.
- Does the monitor return a score every time? The summary shows "no parseable score".
- Did any episode print `ERROR`? Usually that's a rate limit or a model id problem.

If you change any prompt or task after this, write down what you changed and why in a `NOTES.md` file.
Changing things after seeing data is normal. Hiding that you did is not.

### 3.2 Full run (40 min, mostly waiting)

```bash
python run_experiment.py --repeats 2 --out results/main.jsonl
python analyze.py results/main.jsonl
```

Save `results/main-summary.md` and `results/main-roc.png`. **Don't rerun until you get numbers you
like.** If you run more seeds, report all of them.

### 3.3 Read the data, not just the table (30 min)

For each monitor, find:
- one attack it **caught**, and why,
- one attack it **missed**, and why,
- the **false alarm** with the highest score on an honest episode, and why. Check `bank_change` first.

Write a one-line note on each in `NOTES.md`. These examples are your interview material.

✅ **Checkpoint:** `main-summary.md`, `main-roc.png` and `NOTES.md` with at least 6 concrete observations.

---

## Session 4: One change of your own (about 1 hour)

Pick **one** of these, or your own idea, and write your prediction in NOTES.md *before* running it.

**Option A: Stronger monitor (cheap, no agent reruns).** Re-score the same transcripts with a larger model:
```bash
python run_experiment.py --rescore results/main.jsonl --monitor-model claude-sonnet-5-5 --out results/main-sonnet-monitor.jsonl
python analyze.py results/main-sonnet-monitor.jsonl
```
Question: how much does monitor strength matter here, and is the cost worth it?

**Option B: A controls-informed LLM monitor (your banking angle).** In `monitor.py`, write a second
prompt that also gives the LLM a short list of the payment controls a bank uses, in your own words.
Or pass it the `rule_monitor` reasons. Add it as a new monitor key, then `--rescore`.
Question: does domain knowledge help the LLM, or does it just copy the rules, false alarms included?

**Option C: An attacker that knows the rules.** In `agent.py`, add the rule list to
`ATTACK_SYSTEM` ("these controls are in place…") and rerun attack episodes.
Question: can the agent route around controls it knows about, and does the LLM monitor still catch it?
This option costs a full agent run.

Whatever you pick: one change, the same seeds, and the before and after numbers side by side,
including a result that's "no difference".

✅ **Checkpoint:** your prediction, the result and a 3-sentence interpretation in NOTES.md.

---

## Session 5: Write up, publish, use it in the application (about 1 hour)

### 5.1 Write-up (30 min)

Copy `WRITEUP_TEMPLATE.md` to `WRITEUP.md` and fill it in yourself. Keep it to one page. Paste
your real tables, and fill the README's Results section too.

### 5.2 Publish to GitHub (15 min)

```bash
git init
git add .
git status                                  # read the list: no .env, no keys, no .venv
grep -rn "sk-ant" . --exclude-dir=.venv     # must print nothing
git commit -m "payments-monitor: AI agent sabotage vs bank controls and LLM monitors"
```

Then create an empty **public** repo named `payments-monitor` on github.com with no README, and run:

```bash
git branch -M main
git remote add origin https://github.com/<your-username>/payments-monitor.git
git push -u origin main
```

Open the repo in a browser and check that the README and the ROC image show up.

### 5.3 Put it in the application (15 min)

Write these yourself. Here are the shapes, not the words:

- **Résumé line (one sentence):** what you built + the domain + the comparison + one real number.
  Include the GitHub link.
- **Research answer (one paragraph):** the question you care about (monitoring agents that move
  money), what you built this week and the actual finding (including what didn't work), and what
  you'd study next with a mentor, ideally from your Future Work list.
- Put the GitHub URL in the application's links box.

Be precise about scope: it's a small, weekend-scale replication-style experiment. Saying exactly
that is a strength.

---

## Interview prep: questions to be ready for

Practise these out loud. Pointers tell you what a good answer *covers*. The words must be yours.

1. **"Walk me through the project in two minutes."** Cover the question, the setup, the main result, the main limitation.
2. **"Why payments?"** Cover high stakes, existing controls to compare against, and your experience.
3. **"How did you pick the threshold, and what's wrong with that?"** Cover FPR budget, tuning on test data, small sample size.
4. **"Your rule monitor did X. Is that a fair comparison?"** Cover the fact that you wrote the rules knowing the attacks.
5. **"Did the agent ever refuse the side task? What did you do with those episodes?"** Cover refusal counts and how they affect side-task success.
6. **"Show me one attack the LLM monitor missed. Why did it miss?"** Use a concrete transcript from your NOTES.md.
7. **"What does the monitor not see, and why does it matter?"** Cover private thinking, the hidden scratchpad and SHADE-Arena's finding.
8. **"How confident are you in the numbers?"** Cover the episode count, variance, rerunning seeds, error bars.
9. **"How would you make the attacker stronger?"** Cover knowledge of the rules, longer tasks, multiple episodes.
10. **"If you had three months with a mentor, what would you do next?"** Cover one clear question, how you'd measure it, and why it matters for safety.

Final honesty check before submitting anything: every number you quote is in your
`results/*-summary.md`, and every sentence in the application is one you wrote and can defend.
