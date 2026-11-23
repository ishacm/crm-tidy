"""Assign an owner per record with simple rules, and write a short brief for the best ones."""
import itertools
import os

from crm_tidy.config import CONFIG


def _matches(when: dict, r: dict) -> bool:
    for k, v in when.items():
        val = r.get("country") if k == "geo" else r.get(k)
        if isinstance(v, list) and val not in v:
            return False
        if not isinstance(v, list) and val != v:
            return False
    return True


def assign(records: list[dict], rules: list[dict] | None = None) -> None:
    rules = rules or CONFIG["route"]["rules"]
    cycles = {i: itertools.cycle(r["round_robin"]) for i, r in enumerate(rules) if r.get("round_robin")}
    for rec in sorted(records, key=lambda x: -x.get("fit_score", 0)):
        for i, rule in enumerate(rules):
            if _matches(rule.get("when", {}), rec):
                rec["route_owner"] = next(cycles[i]) if i in cycles else rule.get("owner", "")
                break


def brief(r: dict) -> str:
    name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or r.get("email") or "Unknown"
    why = "; ".join(x for x in r.get("reasons", []) if x.startswith("+") and not x.startswith("+0"))
    gaps = ", ".join(r.get("unknown", [])) or "none"
    return (f"*{name}*, {r.get('title') or 'no title'} at {r.get('company') or r.get('domain')} "
            f"({r.get('country') or '?'}). Fit {r.get('fit_score')}/100, tier {r.get('tier')}, owner: {r.get('route_owner')}.\n"
            f"Why: {why or 'n/a'}. Still unknown: {gaps}.")


def slack(records: list[dict], limit: int = 10) -> int:
    url = os.environ.get("SLACK_WEBHOOK_URL")
    top = [r for r in records if r.get("tier") == "A"][:limit]
    if not url or not top:
        return 0
    import httpx
    text = "*crm-tidy: top-tier records*\n\n" + "\n\n".join(brief(r) for r in top)
    try:
        return len(top) if httpx.post(url, json={"text": text}, timeout=15).status_code == 200 else 0
    except Exception:
        return 0
