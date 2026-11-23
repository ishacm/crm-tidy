"""Fill company gaps with a waterfall: free website check -> Apollo (if you have a key) -> Clay (CSV round trip).

Each provider only gets the companies that still have gaps, and every filled field records where it came
from. Apollo has a hard credit cap per run, because its free plan is small.
"""
import csv
import os
from pathlib import Path

from crm_tidy import ROOT, web
from crm_tidy.config import CONFIG
from crm_tidy.llm import complete_json

E = CONFIG["enrich"]
PROMPT = (ROOT / "prompts" / "classify.md").read_text()
APOLLO_BULK = "https://api.apollo.io/api/v1/organizations/bulk_enrich"
GAPS = ("industry", "employees_n", "country")


def companies(records: list[dict]) -> dict:
    """domain -> current company facts (taken from the best record of that company)."""
    out = {}
    for r in records:
        d = r.get("domain")
        if not d:
            continue
        c = out.setdefault(d, {"domain": d, "company": r.get("company"), "industry": "", "employees_n": None,
                               "country": "", "sources": {}})
        for f in GAPS:
            if not c.get(f) and r.get(f):
                c[f] = r[f]
                c["sources"][f] = "crm"
    return out


def missing(c: dict) -> bool:
    return any(not c.get(f) for f in GAPS)


def _fill(c: dict, field: str, value, source: str) -> bool:
    if value in (None, "", "unknown") or c.get(field):
        return False
    c[field] = value
    c["sources"][field] = source
    return True


def website(comps: dict, industries: list[str], pages: dict | None = None) -> dict:
    """Free: read each homepage and classify it. pages = {domain: html} for tests and the demo."""
    todo = [c for c in comps.values() if missing(c)][:E["website"]["max_companies"]]
    stats = {"checked": 0, "filled": 0}
    for i in range(0, len(todo), 8):
        batch, texts = todo[i:i + 8], []
        for c in batch:
            raw = (pages or {}).get(c["domain"]) if pages is not None else web.get(f"https://{c['domain']}")
            texts.append({"domain": c["domain"], "text": web.html_to_text(raw or "", 1500)})
        stats["checked"] += len(batch)
        try:
            out = complete_json(PROMPT.replace("{industries}", ", ".join(industries) or "any")
                                .replace("{companies}", "\n".join(f"- {t['domain']}: {t['text']}" for t in texts)),
                                "classify", context={"companies": texts, "industries": industries})
        except RuntimeError:
            continue
        by = {x.get("domain"): x for x in out.get("items", [])}
        for c in batch:
            x = by.get(c["domain"]) or {}
            n = sum([_fill(c, "industry", x.get("industry"), "website"),
                     _fill(c, "employees_n", x.get("employees_hint"), "website")])
            c["description"] = c.get("description") or x.get("description", "")
            stats["filled"] += n
    return stats


def apollo(comps: dict, http=None) -> dict:
    """Apollo bulk organization enrichment, 10 domains per call, 1 credit per company. Skipped without a key."""
    key = os.environ.get("APOLLO_API_KEY")
    stats = {"enabled": bool(key and E["apollo"]["enabled"]), "credits": 0, "filled": 0, "errors": 0}
    if not stats["enabled"]:
        return stats
    if http is None:
        import httpx
        http = httpx
    todo = [c for c in comps.values() if missing(c)][:E["apollo"]["max_credits_per_run"]]
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]
        try:
            r = http.post(APOLLO_BULK, json={"details": [{"domain": c["domain"]} for c in batch]},
                          headers={"x-api-key": key, "Content-Type": "application/json", "Cache-Control": "no-cache"},
                          timeout=30)
            if r.status_code != 200:
                stats["errors"] += 1
                continue
            data = r.json() or {}
            orgs = data.get("organizations") or data.get("matches") or []
        except Exception:
            stats["errors"] += 1
            continue
        stats["credits"] += len(batch)
        from crm_tidy.clean import domain_of
        by = {}
        for o in orgs:
            if o:  # response shape is not documented in detail, so match on any domain field we find
                by[(o.get("primary_domain") or domain_of(o.get("website_url") or "")).lower()] = o
        for c in batch:
            o = by.get(c["domain"])
            if not o:
                continue
            # Apollo's primary `industry` is broad ("information technology & services" for most software firms);
            # the `industries` list carries the useful labels ("computer software"), so keep all of them for scoring.
            tags = [x.lower() for x in (o.get("industries") or [o.get("industry")]) if x]
            if tags and not c.get("industry_all"):
                c["industry_all"] = ", ".join(dict.fromkeys(tags))
            stats["filled"] += sum([_fill(c, "industry", (o.get("industry") or "").lower(), "apollo"),
                                    _fill(c, "employees_n", o.get("estimated_num_employees"), "apollo"),
                                    _fill(c, "country", _iso(o.get("country")), "apollo")])
    return stats


def _iso(country: str | None) -> str:
    from crm_tidy.clean import norm_country
    return norm_country(country or "")


def clay_export(comps: dict, path: Path) -> int:
    """Write the companies that still have gaps, ready to import into a Clay table."""
    todo = [c for c in comps.values() if missing(c)]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["domain", "company", "missing"])
        for c in todo:
            w.writerow([c["domain"], c.get("company", ""), ", ".join(g for g in GAPS if not c.get(g))])
    return len(todo)


CLAY_COLS = {"industry": ["industry", "company industry", "linkedin industry"],
             "employees_n": ["employee count", "employees", "headcount", "company size", "size"],
             "country": ["country", "hq country", "company country", "location country"]}


def clay_import(comps: dict, path: Path) -> dict:
    """Merge a CSV exported from Clay back in, matched by domain. Column names are matched loosely."""
    from crm_tidy.clean import employees
    stats = {"rows": 0, "filled": 0}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        heads = {h.lower().strip(): h for h in reader.fieldnames or []}
        col = {fld: next((heads[a] for a in al if a in heads), None) for fld, al in CLAY_COLS.items()}
        dcol = heads.get("domain") or heads.get("company domain") or heads.get("website")
        for row in reader:
            stats["rows"] += 1
            from crm_tidy.clean import domain_of
            c = comps.get(domain_of(row.get(dcol, "")) if dcol else "")
            if not c:
                continue
            if col["industry"]:
                stats["filled"] += _fill(c, "industry", (row.get(col["industry"]) or "").lower(), "clay")
            if col["employees_n"]:
                stats["filled"] += _fill(c, "employees_n", employees(row.get(col["employees_n"]) or ""), "clay")
            if col["country"]:
                stats["filled"] += _fill(c, "country", _iso(row.get(col["country"])), "clay")
    return stats


def clay_push(comps: dict, http=None) -> dict:
    """Optional: send gap companies straight into a Clay table via its webhook (needs a plan with webhooks)."""
    url = os.environ.get("CLAY_WEBHOOK_URL")
    if not url:
        return {"enabled": False, "sent": 0}
    if http is None:
        import httpx
        http = httpx
    sent = 0
    for c in [c for c in comps.values() if missing(c)]:
        try:
            if http.post(url, json={"domain": c["domain"], "company": c.get("company", "")}, timeout=15).status_code < 300:
                sent += 1
        except Exception:
            pass
    return {"enabled": True, "sent": sent}


def apply(records: list[dict], comps: dict) -> None:
    for r in records:
        c = comps.get(r.get("domain"))
        if not c:
            continue
        r.setdefault("sources", {})
        for f in GAPS:
            if not r.get(f) and c.get(f):
                r[f] = c[f]
                r["sources"][f] = c["sources"].get(f, "")
        r["company_description"] = c.get("description", "")
        if c.get("industry_all"):
            r["industry_all"] = c["industry_all"]
