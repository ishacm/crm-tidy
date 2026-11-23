"""Deterministic stand-ins for the LLM (CRMTIDY_LLM=mock), for tests, CI and the demo.
Same output contract as the real prompts; rules, not intelligence. Mock output is never a finding."""
import re

import yaml

from crm_tidy import ROOT

INDUSTRY_WORDS = [("software", r"\bsoftware|saas|platform|devtools|developer tools|api\b"), ("e-commerce", r"e-commerce|online store|online shop|shop for"),
                  ("agency", r"\bagency\b"), ("consulting", r"consulting"), ("manufacturing", r"manufactur|robots"),
                  ("health", r"health|clinic"), ("travel", r"travel"), ("nonprofit", r"nonprofit|foundation"),
                  ("restaurants", r"restaurant"), ("security", r"security"), ("expense management", r"expense")]


def _icp(ctx):
    if "Ledgerly" in ctx.get("text", ""):
        icp = yaml.safe_load((ROOT / "fixtures" / "demo" / "icp.yaml").read_text())
        icp.pop("status", None); icp.pop("source_url", None)
        return icp
    return {"company": "Unknown", "sells": "", "industries": [], "employees": {"min": 0, "max": 100000}, "geos": [],
            "personas": [], "seniority": [], "disqualifiers": [], "competitor_domains": []}


def _classify(ctx):
    items = []
    for c in ctx.get("companies", []):
        t = c["text"].lower()
        ind = next((name for name, pat in INDUSTRY_WORDS if re.search(pat, t)), "unknown")
        m = re.search(r"team of (\d+) people", t)
        items.append({"domain": c["domain"], "industry": ind, "b2b": "shop" not in t,
                      "description": c["text"][:80], "employees_hint": int(m.group(1)) if m else None})
    return {"items": items}


def handle(purpose, prompt, ctx):
    return {"icp": _icp, "classify": _classify}[purpose](ctx)
