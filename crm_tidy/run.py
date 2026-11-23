"""Clean, enrich, score and route a CRM export.

  python -m crm_tidy.run --csv contacts.csv --website https://your-company.com     # drafts icp.yaml first
  python -m crm_tidy.run --csv contacts.csv --icp icp.yaml                          # after you've edited it
  python -m crm_tidy.run --csv contacts.csv --icp icp.yaml --clay-import clay_export.csv
  CRMTIDY_LLM=mock python -m crm_tidy.run --demo                                    # fictional data, no key
"""
import argparse
import datetime as dt
import json
from pathlib import Path

import yaml

from crm_tidy import ROOT, clean, enrich, icp as icp_mod, ingest, llm, report, route, score

FIX = ROOT / "fixtures" / "demo"


def run(csv_path, *, website: str | None = None, icp_path=None, clay_csv=None, demo: bool = False,
        out_root: Path | None = None, slack: bool = False) -> dict:
    out = (out_root or ROOT / "runs") / f"{dt.date.today()}-{'demo' if demo else Path(csv_path).stem}"
    out.mkdir(parents=True, exist_ok=True)
    if icp_path:
        icp = icp_mod.load(icp_path)
    else:
        html = (FIX / "homepage.html").read_text() if demo else None
        icp = icp_mod.draft(website or "https://ledgerly.example", html=html)
        icp_mod.save(icp, out / "icp.yaml")
    rows, mapping = ingest.load(csv_path)
    res = clean.run(rows)
    comps = enrich.companies(res["records"])
    pages = json.loads((FIX / "homepages.json").read_text()) if demo else None
    stats = {"website": enrich.website(comps, icp.get("industries", []), pages=pages) if enrich.E["website"]["enabled"] else {},
             "apollo": enrich.apollo(comps)}
    stats["clay"] = enrich.clay_import(comps, Path(clay_csv)) if clay_csv else {"rows": 0, "filled": 0}
    stats["clay"]["push"] = enrich.clay_push(comps)
    stats["clay"]["export_for_clay"] = enrich.clay_export(comps, out / "for_clay.csv")
    enrich.apply(res["records"], comps)
    for r in res["records"]:  # enrichment can add industry after cleaning, so recompute what depends on it
        r.setdefault("sources", {})
    score.run(res["records"], icp)
    route.assign(res["records"])
    res.update({"created": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "mode": llm.mode(),
                "icp": icp, "icp_yaml": yaml.safe_dump(icp, sort_keys=False, allow_unicode=True),
                "mapping": mapping, "enrich": stats})
    res["summary"] = report.summary(res)
    res["files"] = report.write(res, out)
    res["files"]["for_clay"] = str(out / "for_clay.csv")
    if slack:
        res["slack_sent"] = route.slack(sorted(res["records"], key=lambda r: -r["fit_score"]))
    return res


def main():
    ap = argparse.ArgumentParser(description="crm-tidy: clean, enrich, score and route a CRM export.")
    ap.add_argument("--csv", help="CRM export")
    ap.add_argument("--website", help="your company website, to draft the ICP")
    ap.add_argument("--icp", help="an ICP yaml you have reviewed")
    ap.add_argument("--clay-import", help="CSV exported from Clay after enrichment")
    ap.add_argument("--demo", action="store_true", help="fictional data, no network")
    ap.add_argument("--slack", action="store_true", help="post top-tier briefs to SLACK_WEBHOOK_URL")
    a = ap.parse_args()
    csv_path = FIX / "messy_crm.csv" if a.demo and not a.csv else a.csv
    if not csv_path:
        ap.error("--csv is required (or use --demo)")
    r = run(csv_path, website=a.website, icp_path=a.icp, clay_csv=a.clay_import, demo=a.demo, slack=a.slack)
    s = r["summary"]
    print(f"{s['rows_in']} rows -> {s['records_out']} records, {s['duplicates_merged']} duplicates merged, tiers {s['tiers']}")
    print(f"apollo credits used: {s['enrich']['apollo'].get('credits', 0)} · companies still missing data (for Clay): "
          f"{s['enrich']['clay']['export_for_clay']}")
    for k, v in r["files"].items():
        print(f"{k:>9}: {v}")


if __name__ == "__main__":
    main()
