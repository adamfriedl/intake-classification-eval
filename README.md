# intake-classification-eval

Two runs of a model against the "User Intake Classification" dataset (Draft v0.2, May 2026)
from the Stanford Legal Design Lab's Legal Help Commons.
https://www.justicebench.org/dataset/intake-classification-inputs

The dataset is a thoughtful piece of work. Alongside ordinary cases it includes deliberate
tests: messages with crisis words that are not emergencies, messages with no legal issue at all,
people caught between two jurisdictions, hostile or disorganised writers. That makes it a far
better test of an intake tool than a plain list of cases, and it is why I wanted to work with it.

It has 180 synthetic messages from people seeking legal help, each labelled with legal issue
codes (LIST taxonomy), a state and county, and an emergency flag.

## What I found

The main lesson is about the prompt, not the model. The first run's prompt was written before I
had studied how the answer key is labelled; the second follows the key's conventions as far as I
could read them. Changing only the instructions moved several figures by a wide margin.

- **Issue codes: exact matches went from 9% to 23%.** The key usually gives one code at the
  routing level of the taxonomy (e.g. "Eviction from a home"), not the most specific code. The
  first prompt asked for the most specific code and allowed up to three; the model averaged 2.3
  codes against the key's 1.36. The second prompt asks for the routing level, and the model
  averaged 1.44.
- **The lenient measures dipped slightly**, because the first run's extra codes gave it more
  chances to hit one of the key's. They are reported anyway, and are why the exact-set measure
  is the fairer one to compare.
- **Most remaining code misses are still one level apart.** In 59 of the second run's 106
  scenarios with no code right, the model's code was on the same path as the key's, and in 56 of
  those it was the more specific one. For example, it often chose "Answering an eviction
  lawsuit" where the key has "Being a defendant in an eviction lawsuit".
- **Emergencies: the two prompts err in opposite directions.** The first defined an emergency as
  something "within days" and missed 41 of the key's 92 emergencies. The second counts any
  served papers, scheduled hearing or open deadline, and misses 4, but raises 27 false alarms.
  Most of those are benefit denials with an appeal still open, lawsuits with no stated deadline,
  or routine hearings, which the key treats as not urgent. The key's line sits between the two
  prompts; where exactly is a legal judgment I'd want to discuss with the Lab, not tune for.
- **The false-positive tests caught the second prompt's own rule.** It flagged 4 of the 10
  messages with crisis words in a non-urgent context. Each of the 4 mentions a hearing or an
  appeal (one 8 months away), so the model was following the prompt, not reacting to the words.
- **Both runs caught all 10 designed crisis scenarios** (mental health crisis, active
  immigration enforcement, threats of violence, a minor at risk).
- **No legal issue:** the second run correctly gave no code to 7 of the 10 non-legal messages,
  against 4 in the first.

## Which answer key the scoring uses

The dataset file itself is never edited.

- **Issue codes**: the JSON cell, which the dataset page calls the canonical gold label. One
  row's JSON cell does not parse; for that row the LIST Code column is used.
- **County**: matched by name against the Census Bureau's county file, so that a county is right
  whether the model names it or gives its five-digit code.
- **State and emergency**: the spreadsheet columns. The emergency column agrees with the JSON on
  every row where the JSON can be read.

The model's answers for all 180 scenarios are saved for both runs, so they can be rescored
against any later version of the key without rerunning the model.

## The two prompts

Both runs use `claude-sonnet-5-5`, the same output schema, and the same message format (the
intake channel, then the message). Only the instructions differ. Both are in
`scripts/run_baseline.py` and recorded in each run's `.meta.json`.

| | v1 (13 Oct 2026) | v2 (2 Nov 2026) |
|---|---|---|
| Written | Before seeing any answers, and before studying the key | After studying the key's labels and the v1 results |
| Code level | The most specific code the message supports | The routing level, usually the second or third level of LIST; deeper only when the deeper code names the problem itself |
| Number of codes | One in most cases, up to three | One for the main problem; another only for a separate current problem |
| Jurisdiction | Where the problem is, if the message lets you tell | Where the person lives; infer the county from a city, neighbourhood or court |
| Emergency | "a deadline, hearing, lockout, shutoff, or safety risk within days" | Served papers, a scheduled hearing, a notice, any open deadline to answer or appeal, an ongoing loss, or a current safety risk; not past matters, planning, or requests with no notice or deadline |
| Today's date | Not given | Tuesday, 4 November 2025, the date the messages are written as of (several give dates relative to it, such as a hearing "8 days out") |

## Results

| Field | Measure | v1 | v2 |
|---|---|---|---|
| Issue code | Exact set of codes | 17 (9%) | 42 (23%) |
| Issue code | At least one code right | 78 (43%) | 74 (41%) |
| Issue code | Same code or on the same path | 139 (77%) | 133 (74%) |
| Issue code | Right branch (e.g. `HO-02`) | 160 (89%) | 160 (89%) |
| Issue code | Right area (e.g. Housing) | 169 (94%) | 170 (94%) |
| Issue code | Codes per scenario (key: 1.36) | 2.3 | 1.44 |
| State | Right, of 176 | 168 (95%) | 172 (98%) |
| County | Right by name, of 176 | 165 (94%) | 171 (97%) |
| County | Right by FIPS code, of 176 | 165 (94%) | 170 (97%) |
| Emergency | Right, of 180 | 138 (77%) | 149 (83%) |
| Emergency | Key's 92 emergencies the model flagged (recall) | 51 (55%) | 88 (96%) |
| Emergency | Model's flags the key agrees with (precision) | 51 of 52 (98%) | 88 of 115 (77%) |

Issue-code figures are out of 180. Four scenarios have no state or county in the key and are not
scored on those fields.

By the dataset's designed test categories, v1 / v2:

| Category | Scenarios | At least one code right | Same code or on the same path | County right | Emergency right | Emergencies missed | False alarms |
|---|---|---|---|---|---|---|---|
| Ordinary | 136 | 65 / 57 | 110 / 101 | 123 / 128 | 103 / 111 | 32 / 3 | 1 / 22 |
| Confounder | 14 | 5 / 4 | 12 / 13 | 13 / 13 | 5 / 12 | 9 / 1 | 0 / 1 |
| Emergency variation | 10 | 3 / 5 | 7 / 7 | 10 / 10 | 10 / 10 | 0 / 0 | 0 / 0 |
| False-positive emergency | 10 | 1 / 1 | 6 / 5 | 10 / 10 | 10 / 6 | 0 / 0 | 0 / 4 |
| No legal issue | 10 | 4 / 7 | 4 / 7 | 9 / 10 | 10 / 10 | 0 / 0 | 0 / 0 |

"Confounder" covers the dataset's other deliberate tests: an off-topic preamble, several issues
at once, conflicting facts, a hostile or distrustful writer, two jurisdictions.

## How to read these numbers

1. *The prompt is part of what is measured.* That is the point of running both. Neither run's
   figures are a measure of the model alone.
2. *v2 was written with knowledge of the key and of v1's errors.* There is no held-out set: the
   conventions were read from the same 180 scenarios the model is scored on. So v2's figures are
   optimistic, and the useful result is the gap between the runs rather than v2's own scores. The
   prompt was written once and not changed after seeing v2's results. One draft included a time
   limit on deadlines ("within about two months"); I dropped it before the full run because it
   was fitted to a handful of labels rather than a principle. The partial run made with it was
   discarded and is not reported.
3. *Some measures came after seeing v1's results*: the "same path" measure and the breakdown by
   category. Every measure is reported for both runs, not only the favourable ones.
4. *The figures are approximate.* One run per prompt, no repeats, 180 scenarios: differences of
   a few points mean nothing.
5. *There is no human comparison.* Nobody has measured how often two legal aid practitioners
   would choose the same code or the same emergency call for these messages, so there is no
   ceiling to compare against.
6. *The messages are synthetic.* Many state the city, county and state outright; real intake is
   messier.
7. *Not tested*: audience-served tags and special flags, and results by the dataset's difficulty
   rating. The model also sees the intake channel, which the dataset's JSON does not treat as
   part of the input.

**Checks.** The scorer was tested with a perfect and an empty set of answers. A second scorer
(`scripts/check_score.py`), written separately from the scoring rules and sharing no code with
the first, reproduces all 11 accuracy, recall and precision figures in the results table for
both runs; the category breakdown and codes per scenario are not cross-checked. It checks the code, not the rules: a
misreading of a rule shared by both would pass. In v1 the first four scenarios came from an earlier test invocation
with a lower output limit and the same prompt; run details are in `out/runs/*.meta.json`.

The scripts were written with Claude Code, and I reviewed them and the scoring choices. The
reading of the results is mine.

## Data that is not in this repo

Kept out of version control until the Lab agrees to it being republished (the dataset is CC BY 4.0):

- `raw/intake-classification-inputs.csv`: the dataset, exported from its Airtable view on 9 Oct 2026.
  The sha256 of the copy each run used is in `out/runs/<run>.meta.json`.
- `raw/list/terms.json`: the LIST taxonomy feed (as of 16 Jun 2026), from
  https://taxonomy.legal/api/terms
- `out/runs/*-results.xlsx`: results workbooks, which contain the dataset's messages. They are
  rebuilt by the scorer.

`raw/census/national_county2020.txt` is the Census Bureau's 2020 county code file (public domain).

## Scripts

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

    # model runs (need ANTHROPIC_API_KEY; cost money), then scoring
    .venv/bin/python scripts/run_baseline.py --model claude-sonnet-5-5               # v1
    .venv/bin/python scripts/run_baseline.py --model claude-sonnet-5-5 --prompt v2   # v2
    .venv/bin/python scripts/score.py out/runs/claude-sonnet-5-5.jsonl
    .venv/bin/python scripts/score.py out/runs/claude-sonnet-5-5-v2.jsonl

    # rescore a run a second way and compare with score.py (exits 1 on any mismatch)
    .venv/bin/python scripts/check_score.py out/runs/claude-sonnet-5-5-v2.jsonl

`out/runs/<run>.jsonl` holds the model's answers by scenario ID. Scoring reads it, so the
answers can be rescored without calling the model again.

## Licence

The code is MIT licensed (see `LICENSE`). The dataset belongs to the Stanford Legal Design Lab
and is not covered by this licence.
