"""Check the JusticeBench intake-classification gold labels for internal consistency.

Usage: python3 check_gold.py <intake.csv> <list_terms.json> <census_national_county2020.txt>
Returns findings as a list of dicts via collect(); run as a script to print them.
"""
import csv
import json
import re
import sys

CODE = re.compile(r"[A-Z]{2}-\d{2}-\d{2}-\d{2}-\d{2}")
STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


def norm(name):
    return re.sub(r"[^a-z]", "", name.lower().replace("saint", "st"))


def load_census(path):
    by_name, by_fips = {}, {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="|"):
            fips = r["STATEFP"] + r["COUNTYFP"]
            by_name[(r["STATE"], norm(r["COUNTYNAME"]))] = fips
            by_fips[fips] = f'{r["COUNTYNAME"]}, {r["STATE"]}'
    return by_name, by_fips


def json_fips(j):
    st = j.get("fips_state") or (j.get("state") if str(j.get("state", "")).isdigit() else None)
    co = j.get("fips_county") or (j.get("county") if str(j.get("county", "")).isdigit() else None)
    return (str(st) + str(co)) if st and co else None


def collect(csv_path, terms_path, census_path):
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig", newline="")))
    terms = {t["code"]: t for t in json.load(open(terms_path, encoding="utf-8"))["terms"]}
    by_name, by_fips = load_census(census_path)
    fixes, disputes, notes = [], [], []

    def name_of(fips):
        return by_fips.get(fips, "no such county code")

    for r in rows:
        sid = r["Scenario ID"]
        state = STATES.get(r["Jdx it belongs to"].strip())
        county = r["Jurisdiction"].strip()
        truth = by_name.get((state, norm(county))) if state and county else None
        if state and county and not truth:
            notes.append((sid, f"could not match {county!r}, {state} to a Census county"))

        try:
            out = json.loads(r["JSON case profiler"])
        except json.JSONDecodeError as e:
            fixes.append((sid, "JSON case profiler", "does not parse", "re-export as valid JSON",
                          f"Strict JSON parsers reject it: {e.msg.lower().removesuffix(" at")} at character {e.pos} (a raw line break inside a string value)."))
            out = None

        if truth:
            for field in ("FIPS code", "FIPS_code (from Jurisdiction)"):
                cur = r[field].strip()
                if cur and cur != truth:
                    why = (f"Leading zero dropped." if cur.zfill(5) == truth else
                           f"{cur} is {name_of(cur)}; the row's jurisdiction is {county}, {state}.")
                    fixes.append((sid, field, cur, truth, why))
            if out:
                cur = json_fips(out["output"].get("jurisdiction") or {})
                if cur and cur != truth:
                    fixes.append((sid, "JSON case profiler: jurisdiction county code", cur, truth,
                                  f"{cur} is {name_of(cur)}; the row's jurisdiction is {county}, {state}."))

        if not out:
            continue
        if out.get("input", "").strip() != r["User's Query"].strip():
            notes.append((sid, "JSON input differs from User's Query"))
        col = CODE.findall(r["LIST Code (from Legal Issue)"])
        js = CODE.findall(json.dumps(out["output"].get("list_issue_codes") or []))
        for c in set(col) | set(js):
            if c not in terms:
                notes.append((sid, f"code {c} not in LIST feed"))
        if set(col) != set(js):
            disputes.append({
                "sid": sid, "short": r["Expert's Short explanation"], "query": r["User's Query"],
                "col": col, "json": js,
                "only_col": [c for c in col if c not in js], "only_json": [c for c in js if c not in col],
            })
    return rows, terms, fixes, disputes, notes


if __name__ == "__main__":
    rows, terms, fixes, disputes, notes = collect(*sys.argv[1:4])
    print(f"{len(rows)} rows | {len(fixes)} fixes | {len(disputes)} disputed | {len(notes)} notes\n")
    for f in fixes:
        print("FIX ", " | ".join(f))
    print()
    for d in disputes:
        print("DISP", d["sid"], "col-only", [(c, terms[c]["name"]) for c in d["only_col"]],
              "json-only", [(c, terms[c]["name"]) for c in d["only_json"]])
    print()
    for n in notes:
        print("NOTE", " | ".join(n))
