import json

import yaml

from crm_tidy import enrich, route, score
from crm_tidy.clean import clean_record
from crm_tidy.ingest import FIELDS

ICP = yaml.safe_load(open("fixtures/demo/icp.yaml"))


def rec(**kw):
    r = clean_record({f: "" for f in FIELDS} | {"row": 2, "extra": {}} | kw)
    r.update({k: v for k, v in kw.items() if k in ("industry", "employees_n")})
    return r


def test_perfect_fit_scores_100_with_reasons():
    r = rec(title="Head of Finance", email="a@acme.example", country="Germany", industry="software", employees_n=80)
    s = score.score(r, ICP)
    assert s["fit_score"] == 100 and s["tier"] == "A" and len(s["reasons"]) == 5


def test_unknowns_are_listed_not_guessed():
    s = score.score(rec(title="CFO", email="a@acme.example"), ICP)
    assert set(s["unknown"]) == {"industry", "company size", "country"} and s["tier"] in ("C", "D")


def test_competitor_is_zero_and_intern_is_capped():
    assert score.score(rec(title="CFO", email="x@northbook.example", industry="software", employees_n=80, country="US"), ICP)["fit_score"] == 0
    s = score.score(rec(title="Working Student Finance", email="x@acme.example", industry="software", employees_n=80, country="US"), ICP)
    assert s["fit_score"] <= 20


def test_personal_email_costs_points():
    a = score.score(rec(title="CFO", email="x@acme.example", industry="software", employees_n=80, country="US"), ICP)["fit_score"]
    b = score.score(rec(title="CFO", email="x@gmail.com", company="Acme", industry="software", employees_n=80, country="US"), ICP)["fit_score"]
    assert a - b == 10


def test_routing_rules_and_round_robin():
    rs = [{"tier": "A", "country": "US", "fit_score": 90}, {"tier": "A", "country": "DE", "fit_score": 85},
          {"tier": "B", "country": "DE", "fit_score": 60}, {"tier": "B", "country": "US", "fit_score": 58}, {"tier": "D", "fit_score": 5}]
    route.assign(rs)
    assert [r["route_owner"] for r in rs] == ["AE North America", "AE EMEA", "SDR 1", "SDR 2", "Nurture"]


class FakeHTTP:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append((url, json, headers))
        class R:
            status_code = 200
            def __init__(s, body): s._b = body
            def json(s): return s._b
        orgs = [{"primary_domain": d["domain"], "industry": "Computer Software", "estimated_num_employees": 140, "country": "United States"}
                for d in (json or {}).get("details", [])]
        return R({"organizations": orgs})


def test_apollo_is_skipped_without_key(monkeypatch):
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    assert enrich.apollo({"a.example": {"domain": "a.example", "sources": {}}})["enabled"] is False


def test_apollo_waterfall_respects_credit_cap_and_only_fills_gaps(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "test-not-a-real-key")
    monkeypatch.setitem(enrich.E["apollo"], "max_credits_per_run", 12)
    comps = {f"c{i}.example": {"domain": f"c{i}.example", "industry": "", "employees_n": None, "country": "", "sources": {}} for i in range(30)}
    comps["c0.example"]["industry"] = "retail"
    http = FakeHTTP()
    st = enrich.apollo(comps, http=http)
    assert st["credits"] == 12 and len(http.calls) == 2           # 10 + 2, never more than the cap
    assert http.calls[0][2]["x-api-key"] == "test-not-a-real-key" and "details" in http.calls[0][1]
    assert comps["c0.example"]["industry"] == "retail"             # existing data is never overwritten
    assert comps["c1.example"]["employees_n"] == 140 and comps["c1.example"]["sources"]["employees_n"] == "apollo"
    assert comps["c1.example"]["country"] == "US"


def test_clay_round_trip(tmp_path):
    comps = {"a.example": {"domain": "a.example", "company": "A", "industry": "", "employees_n": None, "country": "", "sources": {}},
             "b.example": {"domain": "b.example", "company": "B", "industry": "x", "employees_n": 5, "country": "DE", "sources": {}}}
    n = enrich.clay_export(comps, tmp_path / "out.csv")
    assert n == 1 and "a.example" in (tmp_path / "out.csv").read_text()
    (tmp_path / "back.csv").write_text("Domain,Company,Industry,Employee Count,HQ Country\nhttps://www.a.example,A,Fintech,51-200,France\n")
    st = enrich.clay_import(comps, tmp_path / "back.csv")
    assert st["filled"] == 3 and comps["a.example"]["employees_n"] == 125 and comps["a.example"]["country"] == "FR"
    assert comps["a.example"]["sources"]["industry"] == "clay"


def test_industry_match_is_whole_word():
    assert score._in("Computer & Network Security", ["security"])
    assert not score._in("it", ["security"]) and not score._in("retail", ["e-commerce"])
    assert score._in("E-Commerce", ["e-commerce"])


def test_real_apollo_response_shape_scores_software_companies_correctly(monkeypatch):
    """Shape taken from a real bulk_enrich response (Nov 2026), trimmed to the fields we read.
    Apollo's primary `industry` is broad, so scoring must also look at the `industries` list."""
    sample = json.load(open("tests/fixtures/apollo_bulk_enrich_sample.json"))

    class Real:
        def post(self, url, json=None, headers=None, timeout=None):
            class R:
                status_code = 200
                def json(s): return sample
            return R()

    monkeypatch.setenv("APOLLO_API_KEY", "test-not-a-real-key")
    comps = {d: {"domain": d, "industry": "", "employees_n": None, "country": "", "sources": {}}
             for d in ("n8n.io", "pitch.com", "posthog.com")}
    enrich.apollo(comps, http=Real())
    assert comps["pitch.com"]["industry"] == "online media" and "computer software" in comps["pitch.com"]["industry_all"]
    assert comps["posthog.com"]["country"] == "US" and comps["n8n.io"]["employees_n"] == 150
    icp = {"industries": ["software"], "employees": {"min": 20, "max": 500}, "geos": [], "personas": ["finance"],
           "seniority": ["c_level"]}
    recs = [rec(title="CFO", email=f"cfo@{d}") for d in comps]
    enrich.apply(recs, comps)
    for r in recs:
        s = score.score(r, icp)
        assert any(x.startswith("+30 industry fits") for x in s["reasons"]), (r["domain"], s["reasons"])
