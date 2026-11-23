"""Before/after report: what was wrong, what got fixed, what it cost, and who to call first."""
import csv
import html
import json
import re
from collections import Counter
from pathlib import Path

from crm_tidy.clean import FILLED

LABEL = {"first_name": "first name", "last_name": "last name", "employees_n": "company size", "persona": "persona (from title)"}
EXPORT = [("First Name", "first_name"), ("Last Name", "last_name"), ("Email", "email"), ("Job Title", "title"),
          ("Company Name", "company"), ("Company Domain Name", "domain"), ("Country/Region", "country"),
          ("Phone Number", "phone"), ("Number of Employees", "employees_n"), ("Industry", "industry"),
          ("Persona", "persona"), ("Seniority", "seniority"), ("Fit Score", "fit_score"), ("Fit Tier", "tier"),
          ("Fit Reasons", "reasons"), ("Contact Owner", "route_owner"), ("Merged From Rows", "merged_rows")]


def pct(rows: list[dict], f: str) -> int:
    return round(100 * sum(1 for r in rows if r.get(f) not in ("", None, "unknown")) / max(1, len(rows)))


def summary(res: dict) -> dict:
    before, after = res["before"], res["records"]
    return {
        "rows_in": len(before), "records_out": len(after), "duplicates_merged": len(before) - len(after),
        "invalid_emails": sum(1 for r in before if r["email_status"] == "invalid"),
        "companies_renamed": res.get("companies_renamed", 0),
        "personal_emails": sum(1 for r in after if r.get("free_email")),
        "completeness": {f: [pct(before, f), pct(after, f)] for f in FILLED},
        "tiers": dict(sorted(Counter(r["tier"] for r in after).items())),
        "enrich": res["enrich"],
        "filled_by": dict(Counter(src for r in after for src in (r.get("sources") or {}).values() if src != "crm")),
    }


def markdown(res: dict) -> str:
    s, icp = res["summary"], res["icp"]
    L = [f"# CRM cleanup and fit report: {icp.get('company', '')}", "",
         f"**Run:** {res['created']} · mode `{res['mode']}` · ICP: {icp.get('status', 'edited by you')}", ""]
    if res["mode"] == "mock":
        L += ["> **Demo data.** Fictional companies and people, generated for this demo. It shows the format, not findings.", ""]
    L += ["## At a glance", "",
          f"- **{s['rows_in']}** rows in → **{s['records_out']}** clean records (**{s['duplicates_merged']}** duplicates merged)",
          f"- **{s['invalid_emails']}** invalid email(s) flagged, **{s['personal_emails']}** personal email(s) (gmail etc.) kept but scored lower",
          f"- **{s['companies_renamed']}** company names standardised (one spelling per company)",
          "- Tiers: " + ", ".join(f"**{k}** {v}" for k, v in s["tiers"].items()),
          f"- Apollo credits used: **{s['enrich']['apollo'].get('credits', 0)}** "
          f"({'on' if s['enrich']['apollo'].get('enabled') else 'off, no APOLLO_API_KEY'})",
          "- Fields filled by enrichment: " + (", ".join(f"{k} {v}" for k, v in s["filled_by"].items()) or "none"), "",
          "## Completeness, before and after", "", "*Share of records with the field filled. After = after merging duplicates and enrichment.*", "",
          "| Field | Before | After |", "|---|---|---|"]
    L += [f"| {LABEL.get(f, f.replace('_', ' '))} | {a}% | {b}% |" for f, (a, b) in s["completeness"].items()]
    top = sorted(res["records"], key=lambda r: -r["fit_score"])[:10]
    L += ["", "## Call these first", "", "| Score | Tier | Person | Company | Why | Owner |", "|---|---|---|---|---|---|"]
    for r in top:
        why = "; ".join(x for x in r["reasons"] if not x.startswith("+0"))
        L += [f"| {r['fit_score']} | {r['tier']} | {r.get('first_name', '')} {r.get('last_name', '')}, {r.get('title', '')} | "
              f"{r.get('company') or r.get('domain')} | {why} | {r.get('route_owner', '')} |"]
    if res["merges"]:
        L += ["", "## Duplicates merged", "", "| Kept row | Merged rows | Why |", "|---|---|---|"]
        L += [f"| {m['kept_row']} | {', '.join(map(str, m['merged_rows']))} | {m['reason']} |" for m in res["merges"][:30]]
    issues = [r for r in res["before"] if r["issues"]]
    if issues:
        L += ["", "## Needs a human", "", "| Row | Issue |", "|---|---|"]
        L += [f"| {r['row']} | {', '.join(r['issues'])} |" for r in issues[:30]]
    L += ["", "## The ICP used", "", "```yaml", res["icp_yaml"].strip(), "```", "",
          "*Scores are only as good as the ICP: review `icp.yaml` before acting on them. "
          "Website classification is a model's reading of a homepage and is marked as such per field.*"]
    return "\n".join(L)


def html_page(md: str, title: str) -> str:
    out, in_table, in_list, in_code = [], False, False, False
    def inline(s):
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    for line in md.splitlines():
        if line.startswith("```"):
            out.append("</pre>" if in_code else "<pre>"); in_code = not in_code; continue
        if in_code:
            out.append(html.escape(line) + "\n"); continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                out.append("<table>"); in_table = True
            out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>"); continue
        if in_table:
            out.append("</table>"); in_table = False
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(line[2:])}</li>"); continue
        if in_list:
            out.append("</ul>"); in_list = False
        if line.startswith("#"):
            n = len(line) - len(line.lstrip("#")); out.append(f"<h{n}>{inline(line[n:].strip())}</h{n}>")
        elif line.startswith(">"):
            out.append(f"<blockquote>{inline(line.lstrip('> '))}</blockquote>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    for flag, close in ((in_table, "</table>"), (in_list, "</ul>")):
        if flag:
            out.append(close)
    css = ("body{font:15px/1.6 system-ui,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#1b1a18;background:#f5f1e8}"
           "h2{margin-top:36px;border-top:1px solid #dad3c5;padding-top:18px}table{border-collapse:collapse;width:100%;font-size:13px}"
           "td,th{border-bottom:1px solid #dad3c5;padding:7px;text-align:left;vertical-align:top}"
           "blockquote{border-left:3px solid #b04e1a;margin:0;padding-left:12px}pre{background:#ebe5d8;padding:12px;overflow:auto}"
           "code{background:#ebe5d8;padding:1px 4px}")
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{css}</style></head><body>{"".join(out)}</body></html>'


def write(res: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = markdown(res)
    (out_dir / "report.md").write_text(md)
    (out_dir / "report.html").write_text(html_page(md, "crm-tidy report"))
    with open(out_dir / "clean_crm.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([h for h, _ in EXPORT])
        for r in sorted(res["records"], key=lambda r: -r["fit_score"]):
            w.writerow(["; ".join(map(str, r.get(k) or [])) if isinstance(r.get(k), list) else ("" if r.get(k) is None else r.get(k))
                        for _, k in EXPORT])
    (out_dir / "run.json").write_text(json.dumps({k: v for k, v in res.items() if k != "before"}, indent=2, default=str))
    return {"markdown": str(out_dir / "report.md"), "html": str(out_dir / "report.html"), "csv": str(out_dir / "clean_crm.csv")}
