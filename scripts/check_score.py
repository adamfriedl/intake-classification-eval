"""Check score.py by scoring a run a second way and comparing the figures.

Usage: python3 scripts/check_score.py out/runs/<run>.jsonl

The figures are computed from the README's scoring rules without using any of score.py's code;
only the final comparison imports it. A bug in either scorer shows up as a mismatch. A misreading
of the rules shared by both would not, so this checks the code, not the rules.
"""
import csv
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CODE = re.compile(r"\b[A-Z]{2}(?:-\d\d){4}\b")
STATES = dict(s.rsplit(" ", 1) for s in (
    "Alabama AL|Alaska AK|Arizona AZ|Arkansas AR|California CA|Colorado CO|Connecticut CT|"
    "Delaware DE|District of Columbia DC|Florida FL|Georgia GA|Hawaii HI|Idaho ID|Illinois IL|"
    "Indiana IN|Iowa IA|Kansas KS|Kentucky KY|Louisiana LA|Maine ME|Maryland MD|Massachusetts MA|"
    "Michigan MI|Minnesota MN|Mississippi MS|Missouri MO|Montana MT|Nebraska NE|Nevada NV|"
    "New Hampshire NH|New Jersey NJ|New Mexico NM|New York NY|North Carolina NC|North Dakota ND|"
    "Ohio OH|Oklahoma OK|Oregon OR|Pennsylvania PA|Rhode Island RI|South Carolina SC|"
    "South Dakota SD|Tennessee TN|Texas TX|Utah UT|Vermont VT|Virginia VA|Washington WA|"
    "West Virginia WV|Wisconsin WI|Wyoming WY").split("|"))


def letters(name):
    return "".join(ch for ch in name.lower().replace("saint", "st") if ch.isalpha())


def county_codes():
    lines = (ROOT / "raw/census/national_county2020.txt").read_text(encoding="utf-8").splitlines()
    out = {}
    for line in lines[1:]:
        f = line.split("|")  # STATE|STATEFP|COUNTYFP|COUNTYNS|COUNTYNAME|...
        out[(f[0], letters(f[4]))] = f[1] + f[2]
    return out


def trim(code):
    return re.sub(r"(-00)+$", "", code)


def code_rank(gold, got):
    """0 exact set, 1 shares a code, 2 same path, 3 same branch, 4 same area, 5 wrong."""
    if gold == got:
        return 0
    if not gold:
        return 5
    if gold & got:
        return 1
    if any((trim(g) + "-").startswith(trim(c) + "-") or (trim(c) + "-").startswith(trim(g) + "-")
           for g in gold for c in got):
        return 2
    for width, rank in ((5, 3), (2, 4)):
        if {c[:width] for c in gold} & {c[:width] for c in got}:
            return rank
    return 5


def figures(run_path):
    """{(field, measure): (right, out of)}, using score.py's field and measure names."""
    preds = {}
    for line in open(run_path):
        rec = json.loads(line)
        if rec["pred"] is not None:
            preds[rec["sid"]] = rec["pred"]
    fips = county_codes()
    ranks, state, county, county_fips, emerg = [], [0, 0], [0, 0], [0, 0], [0, 0]
    key_yes = model_yes = both = 0
    for r in csv.DictReader(open(ROOT / "raw/intake-classification-inputs.csv", encoding="utf-8-sig", newline="")):
        p = preds.get(r["Scenario ID"])
        if p is None:
            continue
        try:
            gold = set(CODE.findall(json.dumps(json.loads(r["JSON case profiler"])["output"].get("list_issue_codes"))))
        except ValueError:
            gold = set(CODE.findall(r["LIST Code (from Legal Issue)"]))
        ranks.append(code_rank(gold, {c.strip().upper() for c in p.get("list_issue_codes") or []}))

        key_state = STATES.get(r["Jdx it belongs to"].strip())
        model_state = (p.get("state") or "").strip().upper()
        if key_state:
            state[0] += model_state == key_state
            state[1] += 1
        key_fips = fips.get((key_state, letters(r["Jurisdiction"]))) if key_state and r["Jurisdiction"].strip() else None
        if key_fips:
            county[0] += fips.get((model_state, letters(p.get("county_name") or ""))) == key_fips
            county_fips[0] += (p.get("county_fips") or "").strip() == key_fips
            county[1] += 1
            county_fips[1] += 1

        k, m = r["Emergency?"].strip() == "checked", bool(p.get("is_emergency"))
        emerg[0] += k == m
        emerg[1] += 1
        key_yes, model_yes, both = key_yes + k, model_yes + m, both + (k and m)

    names = ["Exact set of codes", "At least one code right", "Same code or on the same path",
             "Right branch", "Right area"]
    out = {("Issue code", n): (sum(1 for x in ranks if x <= i), len(ranks)) for i, n in enumerate(names)}
    out[("State", "Correct")] = tuple(state)
    out[("County, by name", "Correct")] = tuple(county)
    out[("County, by FIPS code", "Correct")] = tuple(county_fips)
    out[("Emergency", "Correct")] = tuple(emerg)
    out[("Emergency", "Key's emergencies the model flagged (recall)")] = (both, key_yes)
    out[("Emergency", "Model's flags that the key agrees with (precision)")] = (both, model_yes)
    return out


def main(run_path):
    mine = figures(run_path)

    sys.path.insert(0, str(ROOT / "scripts"))
    import score
    rows = list(csv.DictReader(open(score.CSV, encoding="utf-8-sig", newline="")))
    terms = {t["code"]: t for t in json.load(open(score.TERMS, encoding="utf-8"))["terms"]}
    preds = {json.loads(l)["sid"]: json.loads(l)["pred"] for l in open(run_path)}
    preds = {k: v for k, v in preds.items() if v is not None}
    theirs = {(f, m): (right, total) for f, m, right, total, _, _ in
              score.summarise(score.judge(rows, preds, terms, score.load_census(score.CENSUS)))}

    bad = 0
    for key in sorted(set(mine) | set(theirs)):
        a, b = mine.get(key), theirs.get(key)
        ok = a == b
        bad += not ok
        print(f"{'ok  ' if ok else 'DIFF'} {key[0] + ': ' + key[1]:<70} check {a}  score.py {b}")
    print(f"\n{len(mine)} figures compared, {bad} mismatches")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1])
