"""A 0-100 fit score per record, with the reasons written out. Simple weights you can read and change."""
import re

from crm_tidy.config import CONFIG

S = CONFIG["score"]


def _words(s: str) -> set:
    return {w for w in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(w) > 2 or w in ("it", "ai", "hr")}


def _in(value: str, options: list[str]) -> bool:
    """Whole-word overlap, so 'computer & network security' matches 'security' but 'it' never matches 'security'."""
    v = _words(value)
    return bool(v) and any(v & _words(o) for o in options if o)


def score(r: dict, icp: dict) -> dict:
    w, pts, reasons, unknown = S["weights"], 0, [], []
    ind, emp, geo = r.get("industry"), r.get("employees_n"), r.get("country")
    if not ind or ind == "unknown":
        unknown.append("industry")
    elif _in(ind, icp.get("industries", [])):
        pts += w["industry"]; reasons.append(f"+{w['industry']} industry fits ({ind})")
    else:
        reasons.append(f"+0 industry outside ICP ({ind})")
    lo, hi = (icp.get("employees") or {}).get("min") or 0, (icp.get("employees") or {}).get("max") or 10**9
    if emp is None:
        unknown.append("company size")
    elif lo <= emp <= hi:
        pts += w["size"]; reasons.append(f"+{w['size']} size fits ({emp} employees)")
    elif emp < lo:
        reasons.append(f"+0 too small ({emp} employees)")
    else:
        half = w["size"] // 2
        pts += half; reasons.append(f"+{half} larger than ICP ({emp} employees)")
    geos = icp.get("geos") or []
    if not geos:
        pts += w["geo"]; reasons.append(f"+{w['geo']} ICP is global")
    elif not geo:
        unknown.append("country")
    elif geo in geos:
        pts += w["geo"]; reasons.append(f"+{w['geo']} country fits ({geo})")
    else:
        reasons.append(f"+0 country outside ICP ({geo})")
    p, s = r.get("persona"), r.get("seniority")
    if not p:
        unknown.append("job title")
    elif p in icp.get("personas", []):
        pts += w["persona"]; reasons.append(f"+{w['persona']} persona fits ({p})")
    elif p == "founder_exec" and s == "c_level":
        pts += w["persona"] // 2; reasons.append(f"+{w['persona'] // 2} exec at the company")
    else:
        reasons.append(f"+0 persona outside ICP ({p})")
    if s in icp.get("seniority", []):
        pts += w["seniority"]; reasons.append(f"+{w['seniority']} seniority fits ({s})")
    if s == "intern":
        pts = min(pts, 20); reasons.append("capped: intern or student")
    if r.get("free_email"):
        pts -= S["penalties"]["free_email"]; reasons.append(f"-{S['penalties']['free_email']} personal email")
    if not r.get("domain") and not r.get("company"):
        pts -= S["penalties"]["unknown_company"]; reasons.append(f"-{S['penalties']['unknown_company']} no company")
    if r.get("domain") and r["domain"] in (icp.get("competitor_domains") or []):
        pts = 0; reasons.append("0: competitor")
    pts = max(0, min(100, pts))
    t = S["tiers"]
    tier = "A" if pts >= t["A"] else "B" if pts >= t["B"] else "C" if pts >= t["C"] else "D"
    return {"fit_score": pts, "tier": tier, "reasons": reasons, "unknown": unknown}


def run(records: list[dict], icp: dict) -> None:
    for r in records:
        r.update(score(r, icp))
