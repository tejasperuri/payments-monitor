# [Title: your question as a short phrase]

*Author: Tejas Peruri · Date: · Code: https://github.com/<you>/payments-monitor*

> Fill in every section yourself, in your own words. Keep it to about one page.
> Only real numbers from your own runs. Null or negative results are fine and worth stating plainly.

## Question
One or two sentences. What did you want to find out, and why does it matter for AI safety?

## Setup
- Environment: (fake payments back office, tools available)
- Tasks: (number of main tasks, side tasks, honest and attack episodes, seeds)
- Agent model: · Monitor model(s): · Monitor views:
- Rule-based monitor: (one line on what it checks)
- Metric definitions: (AUC; catch rate at ≤ __% FPR; undetected successful sabotage)

## Results
Paste your table from `results/<run>-summary.md` and link the ROC plot.

| monitor | AUC | catch rate @ __% FPR | undetected sabotage |
|---|---|---|---|
| | | | |

Agent: main-task success honest __ / attack __; side-task success __; refusals __.

## What surprised me
2–4 bullets, each tied to a specific episode you looked at.

## My own experiment (Session 4)
Prediction → what I changed → result → interpretation.

## Limitations
Be specific: sample size, rules written knowing the attacks, threshold tuned on the same data, simple environment, ...

## Next steps
What you would study next, and how you would measure it.
