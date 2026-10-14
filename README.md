# intake-classification-eval

A review of the answer key in the "User Intake Classification" dataset (Draft v0.2, May 2026)
from the Stanford Legal Design Lab's Legal Help Commons, and a first pass at scoring a model
against it.
https://www.justicebench.org/dataset/intake-classification-inputs

The dataset is a thoughtful piece of work. Alongside ordinary cases it includes deliberate
tests: messages with crisis words that are not emergencies, messages with no legal issue at all,
people caught between two jurisdictions, hostile or disorganised writers. That makes it a far
better test of an intake tool than a plain list of cases, and it is why I wanted to work with it.

## What I found

- **Proposed corrections to the answer key.** Checking the labels against the LIST code list and
  the Census county file turned up 46 proposed corrections, nearly all county codes, and 21 rows
  where the dataset's two copies of the issue codes differ. I've shared these with the Lab.
- **Issue codes: most of the model's misses were a more specific code on the same path.** In 61
  of its 102 misses the model named a code on the same path as the key's in the taxonomy, and in
  58 of those its code was the more specific one. My prompt asked for the most specific code the
  message supports, which the key does not always use.
- **Emergencies: my prompt's definition was narrower than the key's.** I defined an emergency as
  something "within days". Looking at the 41 cases where the model and the key disagree, I think
  the key's broader standard is the right one for legal aid intake, so the emergency figures
  mostly measure the gap between the two definitions.
- **The model flagged every designed crisis scenario.** It caught all 10 emergency-variation scenarios (mental
  health crisis, active immigration enforcement, threats of violence, a minor at risk), and was
  not fooled by any of the 10 messages with crisis words in a non-urgent context, though the
  narrow definition makes the second easier.
- **Next:** a run with a prompt that follows the key's conventions, so that the figures measure
  the model and not my choices.

## How this came about

The dataset has 180 synthetic messages from people seeking legal help, each labelled with
legal issue codes (LIST taxonomy), a state and county, and an emergency flag. Before running
any model against it, I checked the labels against two outside sources: the LIST code list and
the Census Bureau's county code file. That turned up:

- 46 proposed corrections, nearly all county codes that do not match the county the row names;
- 21 rows where the dataset's two copies of the issue codes (a spreadsheet column and a JSON
  cell) disagree;
- 18 smaller inconsistencies that do not change a label.

I sent these to the Lab as proposed corrections on 12 Oct 2026. The Lab has not yet said which
it accepts.

## Which answer key the scoring uses

The dataset file itself is never edited.

- **Issue codes**: the JSON cell, which the dataset page calls the canonical gold label. Figures
  are also given for the 159 rows where the spreadsheet column agrees with it.
- **County**: the Census code for the county each row names. This is the one place the scoring
  uses my corrections instead of the published codes.
- **State and emergency**: the spreadsheet columns as published. The emergency column agrees
  with the JSON on every row where the JSON can be read.

The model's answers for all 180 scenarios are saved, so they can be rescored against any later
version of the key without rerunning the model.

## First pass

One run of `claude-sonnet-5-5` on 13 Oct 2026. The prompt was written before seeing any answers,
but also before the key's conventions had been studied, so several of its choices do not match
the key (see "How to read these numbers"). I've kept the run as it is because it shows
how much those choices matter. A run with a prompt that follows the key's
conventions has not been done.

| Field | Measure | All 180 | 159 undisputed rows |
|---|---|---|---|
| Issue code | Exact set of codes | 17 (9%) | 17 (11%) |
| Issue code | At least one code right | 78 (43%) | 72 (45%) |
| Issue code | Same code or on the same path | 139 (77%) | 119 (75%) |
| Issue code | Right branch (e.g. `HO-02`) | 160 (89%) | 140 (88%) |
| Issue code | Right area (e.g. Housing) | 169 (94%) | 148 (93%) |

| Field | Right | Out of | |
|---|---|---|---|
| State | 168 | 176 | 95% |
| County, by name | 165 | 176 | 94% |
| County, by FIPS code | 165 | 176 | 94% |
| Emergency | 138 | 180 | 77% |
| Emergency: key's emergencies the model flagged (recall) | 51 | 92 | 55% |
| Emergency: model's flags the key agrees with (precision) | 51 | 52 | 98% |

By the dataset's designed test categories:

| Category | Scenarios | At least one code right | Same code or on the same path | County right | Emergency right | Emergencies missed | False alarms |
|---|---|---|---|---|---|---|---|
| Ordinary | 136 | 65 | 110 | 123 | 103 | 32 | 1 |
| Confounder | 14 | 5 | 12 | 13 | 5 | 9 | 0 |
| Emergency variation | 10 | 3 | 7 | 10 | 10 | 0 | 0 |
| False-positive emergency | 10 | 1 | 6 | 10 | 10 | 0 | 0 |
| No legal issue | 10 | 4 | 4 | 9 | 10 | 0 | 0 |

"Confounder" covers the dataset's other deliberate tests: an off-topic preamble, several issues
at once, conflicting facts, a hostile or distrustful writer, two jurisdictions.

The model was not fooled by any of the 10 false-positive emergencies (crisis words in a
non-urgent message), though a narrow emergency definition makes that easier. It gave a legal
code to 6 of the 10 scenarios the key marks as not legal problems.

## How to read these numbers

**Assumptions.** The dataset page names four things to extract: issue codes, jurisdiction,
audience-served tags and an emergency flag. A prompt still has to settle details such as how
specific a code should be and what counts as an emergency. The run made these choices:

- The model sees the person's message and the intake channel. The dataset's JSON treats the
  message alone as the input.
- The prompt asks for the most specific code the message supports, and defines an emergency as
  "a deadline, hearing, lockout, shutoff, or safety risk within days".
- The prompt does not give today's date, so the model cannot tell how far away a dated hearing
  or deadline is. A rerun should choose a date and state it.
- Audience-served tags and special flags are not tested, and results are not broken down by the
  dataset's difficulty rating.

**Limits.**

1. *The prompt is part of what is measured.* On issue codes, the key often uses a broad code
   where the prompt asks for a specific one. On emergencies, the key marks about half of all
   scenarios urgent, including a debt suit with a 28-day answer deadline and a scheduled custody
   hearing, where the prompt asked for "within days". For legal aid intake the key's standard is
   the better one: a served summons needs prompt action whatever the deadline, because the cost
   of missing it is high and finding an advocate takes time. So the emergency figures mostly
   measure the gap between two definitions, and they flatter the model's precision.
2. *Nothing has been tuned, but some measures came later.* The prompt was not changed after
   seeing results. Two parts of the scoring were added after seeing them: the "same path"
   measure and the breakdown by category. Every measure is reported, not only the favourable
   ones.
3. *The figures are approximate.* One run, no repeat, 180 scenarios: differences of a few points
   mean nothing.
4. *There is no human comparison.* Nobody has measured how often two legal aid practitioners
   would choose the same code for these messages, so there is no ceiling to compare against.
5. *The messages are synthetic.* Many state the city, county and state outright; real intake is
   messier.
6. *The lenient measures reward listing more codes.* The model averaged 2.3 codes per scenario
   against the key's 1.36, and only the exact-set measure penalises extras.

**Checks.** The scorer was tested with a perfect and an empty set of answers. Its figures on the
159 undisputed rows were reproduced exactly by a second scorer written independently from
plain-language rules. The 180-row figures use the same code with the JSON as the key; the
independent scorer computed one of them (139 on the same path) and matched. The first four
scenarios came from an earlier test invocation with a lower output limit and the same prompt;
the run details are in `out/runs/claude-sonnet-5-5.meta.json`.

The scripts were written with Claude Code, and I reviewed them and the scoring choices. The
reading of the results is mine.

## Data that is not in this repo

Kept out of version control until the Lab agrees to it being republished (the dataset is CC BY 4.0):

- `raw/intake-classification-inputs.csv`: the dataset, exported from its Airtable view on 9 Oct 2026.
  The sha256 of the copy each run used is in `out/runs/<model>.meta.json`.
- `raw/list/terms.json`: the LIST taxonomy feed (as of 16 Jun 2026), from
  https://taxonomy.legal/api/terms
- `out/*.xlsx`, `out/runs/*-results.xlsx`: workbooks, which contain the dataset's messages.
  Both are rebuilt by the scripts.

`raw/census/national_county2020.txt` is the Census Bureau's 2020 county code file (public domain).

## Scripts

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

    # consistency checks on the answer key, and the review workbook
    .venv/bin/python scripts/check_gold.py raw/intake-classification-inputs.csv raw/list/terms.json raw/census/national_county2020.txt
    .venv/bin/python scripts/build_review.py raw/intake-classification-inputs.csv raw/list/terms.json raw/census/national_county2020.txt out/intake-classification-gold-label-review.xlsx

    # model run (needs ANTHROPIC_API_KEY; costs money), then scoring
    .venv/bin/python scripts/run_baseline.py --model claude-sonnet-5-5
    .venv/bin/python scripts/score.py out/runs/claude-sonnet-5-5.jsonl

`out/runs/<model>.jsonl` holds the model's answers by scenario ID. Scoring reads it, so the
answers can be rescored without calling the model again.

## Licence

The code is MIT licensed (see `LICENSE`). The dataset belongs to the Stanford Legal Design Lab
and is not covered by this licence.
