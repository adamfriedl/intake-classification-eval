"""Build the gold-label review workbook from check_gold findings.

Usage: python3 build_review.py <intake.csv> <list_terms.json> <census_national_county2020.txt> <out.xlsx>
"""
import json
import sys
from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from check_gold import collect

FONT = "Arial"
HEAD_FILL = PatternFill("solid", start_color="1F3864")
INPUT_FILL = PatternFill("solid", start_color="FFFF00")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
SHORT_TOP = {"Traffic and Cars", '"Money, Debt and Consumer Issues"', "Public Benefits", "Crime and Prisons", "Rights"}


def fix_type(field, why):
    if field == "JSON case profiler":
        return "Invalid JSON"
    if why.startswith("Leading zero"):
        return "County code: leading zero dropped"
    if field.startswith("JSON"):
        return "County code wrong in JSON"
    if field == "FIPS code":
        return "County code wrong in 'FIPS code' column"
    return "County code wrong in lookup column"


def table(ws, top, headers, rows, widths, input_cols=()):
    for c, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=top, column=c, value=h)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill, cell.alignment, cell.border = HEAD_FILL, WRAP, BORDER
        ws.column_dimensions[get_column_letter(c)].width = w
    for r, row in enumerate(rows, top + 1):
        for c, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font, cell.alignment, cell.border = Font(name=FONT), WRAP, BORDER
            cell.number_format = "@"
            if c in input_cols:
                cell.fill = INPUT_FILL
    ws.freeze_panes = ws.cell(row=top + 1, column=2)
    ws.auto_filter.ref = f"A{top}:{get_column_letter(len(headers))}{top + len(rows)}"


def text(ws, row, value, bold=False, size=10, width_cols=1):
    cell = ws.cell(row=row, column=1, value=value)
    cell.font = Font(name=FONT, bold=bold, size=size)
    cell.alignment = Alignment(wrap_text=width_cols > 1, vertical="top")
    if width_cols > 1:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=width_cols)
    return cell


def main(csv_path, terms_path, census_path, out_path):
    rows, terms, fixes, disputes, _ = collect(csv_path, terms_path, census_path)
    label = lambda codes: "\n".join(f"{c}  {terms[c]['name']}" for c in codes)
    wb = Workbook()

    # Fixes
    fx = wb.active
    fx.title = "Fixes"
    def confounder(sid):
        try:
            return json.loads(by_id[sid]["JSON case profiler"])["output"].get("confounder_type") or ""
        except json.JSONDecodeError:
            return ""

    by_id = {r["Scenario ID"]: r for r in rows}
    fix_rows = [(sid, fix_type(field, why), field, cur, new, why, confounder(sid)) for sid, field, cur, new, why in fixes]
    table(fx, 1, ["Scenario ID", "Type", "Field", "Current value", "Proposed value", "Why",
                  "Confounder type in JSON (blank = ordinary case)"],
          fix_rows, [18, 34, 40, 16, 22, 70, 34])

    # Disputed codes
    dp = wb.create_sheet("Disputed codes")
    text(dp, 1, "Rows where the 'LIST Code (from Legal Issue)' column and the codes inside 'JSON case profiler' "
                "disagree. The dataset page calls the JSON the canonical gold label, so these may just be a stale column; your call.", bold=True, width_cols=9)
    text(dp, 2, "Fill in the yellow column: which answer is gold for that row. Example entries: \"column\", "
                "\"JSON\", \"both\", or the code(s) you want, e.g. \"FA-04-09-00-00; FA-07-01-00-00\".", width_cols=9)
    dp.row_dimensions[1].height = dp.row_dimensions[2].height = 30

    def pattern(d):
        if d["only_col"] and d["only_json"]:
            extra = [c for c in d["only_json"] if c != "FA-04-00-00-00"]
            return "Column has the child code, JSON has its parent" + (" (JSON also adds a code)" if extra else "")
        return "JSON adds a code the column does not have"

    disp_rows = [(d["sid"], pattern(d), label(d["col"]), label(d["json"]), label(d["only_col"]),
                  label(d["only_json"]), "", d["short"], d["query"]) for d in disputes]
    table(dp, 4, ["Scenario ID", "Pattern", "LIST Code column", "JSON profiler codes", "Only in column",
                  "Only in JSON", "Which is gold? (please fill in)", "Expert's short explanation", "User's query"],
          disp_rows, [18, 30, 42, 42, 34, 42, 26, 45, 90], input_cols=(7,))

    # Other observations
    ob = wb.create_sheet("Other observations")
    text(ob, 1, "Lower-priority inconsistencies. None of these change a label; they affect anyone parsing the file.",
         bold=True, width_cols=4)
    obs = []
    shapes, jshapes = Counter(), Counter()
    for r in rows:
        try:
            j = json.loads(r["JSON case profiler"])
        except json.JSONDecodeError:
            continue
        if j.get("input", "").strip() != r["User's Query"].strip():
            obs.append((r["Scenario ID"], "JSON 'input' text differs from the 'User's Query' column",
                        r["User's Query"], j.get("input", "")))
        o = j["output"]
        kinds = {type(x).__name__ for x in o.get("list_issue_codes") or []}
        shapes["bare code strings" if kinds == {"str"} else "{code, label} objects" if kinds == {"dict"} else
               "empty" if not kinds else "mixed"] += 1
        jd = o.get("jurisdiction") or {}
        jshapes["FIPS digits in 'state'/'county'" if "fips_state" not in jd else
                "names in 'state'/'county' plus 'fips_state'/'fips_county'"] += 1
    for r in rows:
        if r["Top Parent Issue"] in SHORT_TOP:
            obs.append((r["Scenario ID"], "'Top Parent Issue' uses the long LIST name where other rows use a short form",
                        r["Top Parent Issue"], ""))
    obs.append(("(whole file)", "'list_issue_codes' comes in two shapes", "; ".join(f"{k}: {v} rows" for k, v in shapes.items()), ""))
    obs.append(("(whole file)", "'jurisdiction' object comes in two shapes", "; ".join(f"{k}: {v} rows" for k, v in jshapes.items()), ""))
    blank = sum(1 for r in rows if not r["Difficulty"].strip())
    obs.append(("(whole file)", "'Difficulty' is blank on some rows", f"{blank} rows", ""))
    table(ob, 3, ["Scenario ID", "Observation", "Column value / detail", "JSON value"], obs, [18, 52, 80, 80])

    # Summary (first tab)
    sm = wb.create_sheet("Summary", 0)
    sm.column_dimensions["A"].width, sm.column_dimensions["B"].width = 62, 12
    text(sm, 1, "User Intake Classification labeled dataset: gold-label review", bold=True, size=14)
    text(sm, 2, "Prepared by Adam Friedl, 9 October 2026")
    text(sm, 3, "File reviewed: 'User Case Profile Inputs.csv', exported from the JusticeBench Airtable view on "
                "9 October 2026 (180 rows, 23 columns). Dataset page: Legal Help User Profiles v0.2, May 2026.")
    text(sm, 5, "Proposed fixes (tab 'Fixes')", bold=True)
    r = 6
    for t in ["County code wrong in JSON", "County code wrong in 'FIPS code' column",
              "County code wrong in lookup column", "County code: leading zero dropped", "Invalid JSON"]:
        text(sm, r, t)
        sm.cell(row=r, column=2, value=sum(1 for f in fix_rows if f[1] == t)).font = Font(name=FONT)
        r += 1
    text(sm, r, "Total proposed fixes", bold=True)
    sm.cell(row=r, column=2, value=len(fix_rows)).font = Font(name=FONT, bold=True)
    r += 1
    text(sm, r, "Distinct scenarios affected", bold=True)
    sm.cell(row=r, column=2, value=len({f[0] for f in fix_rows})).font = Font(name=FONT, bold=True)
    r += 2
    text(sm, r, "Decision needed (tab 'Disputed codes')", bold=True)
    r += 1
    text(sm, r, "Rows where the LIST code column and the JSON codes disagree")
    sm.cell(row=r, column=2, value=len(disp_rows)).font = Font(name=FONT)
    r += 1
    text(sm, r, "  of which: column has the child code, JSON has its parent")
    sm.cell(row=r, column=2, value=sum(1 for d in disp_rows if d[1].startswith('Column has'))).font = Font(name=FONT)
    r += 1
    text(sm, r, "  of which: JSON adds a code the column does not have")
    sm.cell(row=r, column=2, value=sum(1 for d in disp_rows if d[1].startswith('JSON adds'))).font = Font(name=FONT)
    r += 2
    text(sm, r, "What held up", bold=True)
    ncodes = len({c for d in [r_["LIST Code (from Legal Issue)"] for r_ in rows] for c in __import__("re").findall(r"[A-Z]{2}-\d{2}-\d{2}-\d{2}-\d{2}", d)})
    for line in [
        f"All {ncodes} distinct LIST codes in the code column exist in the current LIST feed (as of Jun 16, 2026).",
        "The 'Emergency?' column matches 'is_emergency' in the JSON on all 179 rows whose JSON parses.",
        "All 180 rows are flagged Synthetic.",
    ]:
        r += 1
        text(sm, r, line)
    r += 2
    text(sm, r, "How county codes were checked", bold=True)
    for line in [
        "Each row's state and county name ('Jdx it belongs to' + 'Jurisdiction') was looked up in the Census Bureau's 2020 county code file.",
        "Source: https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt",
        "For every flagged row, the place named in the query text agrees with the 'Jurisdiction' column, so the name is treated as correct and the code as wrong.",
        "LIST feed: https://taxonomy.legal/api/terms",
        "None of the fixes touch a deliberate test condition. Where a flagged row is a confounder or negative case, its type is shown on the Fixes tab; none is a jurisdiction test, and the two multi-jurisdiction confounders (NM-FA-9014, OH-FA-9020) are not flagged.",
        "In rows whose JSON carries both a county name and a county code, the wrong code contradicts the name in the same JSON object.",
    ]:
        r += 1
        text(sm, r, line)
    wb.save(out_path)
    print(f"wrote {out_path}: {len(fix_rows)} fixes, {len(disp_rows)} disputed, {len(obs)} observations")


if __name__ == "__main__":
    main(*sys.argv[1:5])
