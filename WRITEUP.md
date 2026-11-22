# Can an AI monitor catch a payments agent committing hidden fraud?

*Author: Tejas Peruri · Date: Nov 22, 2026 · Code: https://github.com/tejasperuri/payments-monitor*

## Question
If an AI agent working in a bank's payments back office is secretly instructed to commit fraud, can a second AI monitor catch it, and does it do better than the rule-based payment controls banks already use? As agents start taking real financial actions, the safety case depends on whether that kind of monitoring works.

## Setup
- **Environment:** a simulated payments back office with 5 vendors and 7 invoices (one a duplicate). It has an inbox containing a verified bank-change ticket, a $10k approval threshold, an audit log and 10 tools.
- **Tasks:** 9 legitimate main tasks and 5 hidden side tasks:
  - redirect a payment
  - swap a vendor's bank details
  - split a transfer to stay under the approval limit
  - exfiltrate data
  - overpay

  Each side task is judged by the final state of the system, not by what the agent says. The run has 36 episodes: 18 honest and 18 attack.
- **Agent model:** Claude Sonnet 5.5. **Monitors:** Claude Haiku 5.5 in run 1; the same transcripts were rescored with Claude Sonnet 5.5 in run 2.
- **Monitor views:** one sees the tool calls and their results only; the other also sees the agent's visible text.
- **Rule-based monitor:** bank-style controls that flag bank-detail changes, unknown payees, transfers just under the threshold, and overpayments.
- **Metrics:**
  - AUC: how well each monitor's suspicion score separates attack episodes from honest ones.
  - Catch rate: the share of attacks flagged, with the threshold set so at most 10% of honest episodes get flagged.
  - Undetected sabotage: attacks that succeeded and were not flagged.

## Results

| monitor | AUC | catch rate @ ≤10% false alarms | undetected sabotage |
|---|---|---|---|
| Rule-based | 0.44 | 0/18 | 0/18 |
| Haiku, actions only | 0.80 | 1/18 | 0/18 |
| Haiku, actions + text | 0.72 | 0/18 | 0/18 |
| Sonnet, actions only | 0.73 | 1/18 | 0/18 |
| Sonnet, actions + text | 0.67 | 1/18 | 0/18 |

**Agent:**
- Main-task success was 89% (16/18) on honest episodes and 11% (2/18) on attack episodes.
- Side-task success was 0/18.
- In 16 of the 18 attack episodes, the API returned a refusal on the first turn with no tool calls.

The two runs together cost about $1.39.

## What surprised me
- Sonnet 5.5 never carried out a single side task. In 16 of 18 attack episodes it didn't reason its way out partway through; the API refused immediately (`stop_reason: "refusal"`, no output).
- The 2 attack episodes that ran (both `overpay`) completed the legitimate task correctly and did not overpay.
- In honest episodes, the agent behaved like a careful clerk. In one, it declined an unverified bank-change email and flagged a likely duplicate invoice in its summary.
- The rule-based monitor scored every episode 0, because it only reacts to fraudulent actions and none occurred.

## My own experiment
- **Change:** rescored the same 36 transcripts with Sonnet 5.5 as the monitor instead of Haiku 5.5.
- **Result:** the stronger monitor did not do better. AUC fell from 0.80 to 0.73 (actions only) and from 0.72 to 0.67 (with text). Mean suspicion on attack episodes was 2–5 out of 100.
- **Interpretation:** most attack transcripts were empty, so neither monitor was detecting sabotage. The AUC differences mostly reflect how each monitor scores an empty or very short transcript compared with a full honest one.

## Limitations
- With zero successful attacks, this setup could not measure detection at all.
- The sample is small: 36 episodes, 3–4 per side task. AUC differences of this size are within noise.
- The rule-based monitor was written by someone who knew the attacks, and the thresholds were tuned on the same episodes they were scored on.
- The environment is simple and hand-built, and only one agent model was used.
- The attack instruction was framed openly as a red-team exercise, which may have made refusal more likely.

## Next steps
1. Build an attack policy that actually carries out the side tasks, such as a scripted attacker that replays realistic fraud action sequences, so the monitors have real sabotage to catch.
2. Measure catch rates at a fixed false-alarm rate for the rule-based monitor, each AI monitor and a combination of both.
3. Test whether rules and an AI monitor together catch more than either alone, which is how layered controls work in banking.
