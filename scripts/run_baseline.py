"""Run a plain-prompt model baseline over the JusticeBench intake-classification scenarios.

Usage: python3 scripts/run_baseline.py --model claude-sonnet-5-5 [--limit 5]
Needs ANTHROPIC_API_KEY. Appends one JSON line per scenario to out/runs/<model>.jsonl and
skips scenarios already there, so an interrupted run can be restarted. Score with score.py.

The model sees only the user's query and the intake channel, plus the LIST code list.
It never sees the expert explanations or any label.
"""
import argparse
import csv
import datetime
import hashlib
import json
import pathlib
import sys

import anthropic

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV = ROOT / "raw/intake-classification-inputs.csv"
TERMS = ROOT / "raw/list/terms.json"

INSTRUCTIONS = """You are the intake classifier for a legal help service. A person has written in. \
Read their message and record:

1. The legal issue codes that fit, from the LIST taxonomy below. Pick the most specific code \
that the message supports. Give one code in most cases, up to three if the person clearly has \
separate issues. Give none if the message is not about a legal problem.
2. The US state and county the person's problem is in, if the message lets you tell. \
Leave a field empty if you cannot tell.
3. Whether this is an emergency: a deadline, hearing, lockout, shutoff, or safety risk within days.

Use only codes that appear in the list. Each line is CODE<tab>NAME.

LIST taxonomy:
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "list_issue_codes": {"type": "array", "items": {"type": "string"}},
        "state": {"type": "string", "description": "Two-letter postal abbreviation, or empty."},
        "county_name": {"type": "string", "description": "County name, e.g. 'Cook County', or empty."},
        "county_fips": {"type": "string", "description": "Five-digit county FIPS code, or empty."},
        "is_emergency": {"type": "boolean"},
    },
    "required": ["list_issue_codes", "state", "county_name", "county_fips", "is_emergency"],
    "additionalProperties": False,
}


def system_prompt():
    terms = json.load(open(TERMS, encoding="utf-8"))["terms"]
    lines = "\n".join(f'{t["code"]}\t{t["name"]}' for t in sorted(terms, key=lambda t: t["code"]))
    # The code list is the same for every scenario, so cache it.
    return [{"type": "text", "text": INSTRUCTIONS + lines, "cache_control": {"type": "ephemeral"}}]


MAX_TOKENS = 4000
MESSAGE_FORMAT = "Channel: <Input-Channel>, blank line, Message: <User's Query>"


def run_details(model):
    """What a reader needs to know about a run: the prompt, the date, and which data it used."""
    return {
        "model": model,
        "date": datetime.date.today().isoformat(),
        "dataset_sha256": hashlib.sha256(CSV.read_bytes()).hexdigest(),
        "list_as_of": json.load(open(TERMS, encoding="utf-8")).get("as_of"),
        "list_sha256": hashlib.sha256(TERMS.read_bytes()).hexdigest(),
        "max_tokens": MAX_TOKENS,
        "instructions": INSTRUCTIONS,
        "message_format": MESSAGE_FORMAT,
        "schema": SCHEMA,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--limit", type=int, help="only run the first N scenarios not yet done")
    args = ap.parse_args()

    out = ROOT / "out/runs" / f"{args.model}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["sid"] for line in open(out)} if out.exists() else set()
    meta_path, details = out.with_suffix(".meta.json"), run_details(args.model)
    if meta_path.exists():
        old = json.load(open(meta_path))
        # One results file must come from one prompt and one dataset, or the scores mean nothing.
        changed = [k for k in ("instructions", "message_format", "schema", "dataset_sha256", "list_sha256", "max_tokens") if old.get(k) != details[k]]
        if changed:
            sys.exit(f"{out.name} was made with a different {', '.join(changed)}. Move or delete it and its .meta.json first.")
    else:
        json.dump(details, open(meta_path, "w"), indent=1)
    rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8-sig", newline=""))
            if r["Scenario ID"] not in done]
    if args.limit:
        rows = rows[:args.limit]

    client = anthropic.Anthropic()
    system = system_prompt()
    with open(out, "a") as f:
        for i, r in enumerate(rows, 1):
            msg = client.messages.create(
                model=args.model,
                max_tokens=MAX_TOKENS,
                system=system,
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user", "content": "Channel: " + r["Input-Channel"]
                           + "\n\nMessage:\n" + r["User's Query"]}],
            )
            text = next((b.text for b in msg.content if b.type == "text"), "")
            try:
                pred = json.loads(text)
            except json.JSONDecodeError:
                pred = None
            if pred is None:
                # Not recorded, so a rerun will try this scenario again.
                print(f'{i}/{len(rows)} {r["Scenario ID"]} no usable answer (stop: {msg.stop_reason})')
                continue
            u = msg.usage
            f.write(json.dumps({
                "sid": r["Scenario ID"], "model": args.model, "pred": pred, "stop": msg.stop_reason,
                "usage": {"in": u.input_tokens, "out": u.output_tokens,
                          "cache_read": u.cache_read_input_tokens, "cache_write": u.cache_creation_input_tokens},
            }) + "\n")
            f.flush()
            print(f'{i}/{len(rows)} {r["Scenario ID"]} {pred and pred.get("list_issue_codes")}')


if __name__ == "__main__":
    main()
