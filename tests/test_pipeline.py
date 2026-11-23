import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crm_tidy import llm
from crm_tidy.run import FIX, run
from crm_tidy.serve import app


def test_demo_end_to_end(tmp_path):
    r = run(FIX / "messy_crm.csv", demo=True, out_root=tmp_path)
    s = r["summary"]
    assert s["rows_in"] == 60 and s["duplicates_merged"] >= 5 and s["records_out"] == s["rows_in"] - s["duplicates_merged"]
    assert s["completeness"]["industry"][1] > s["completeness"]["industry"][0]
    md = Path(r["files"]["markdown"]).read_text()
    assert "Demo data." in md and "Call these first" in md
    header = Path(r["files"]["csv"]).read_text().splitlines()[0]
    assert header.startswith("First Name,Last Name,Email") and "Fit Score" in header
    assert all(rec["tier"] == "D" or rec["domain"] != "northbook.example" for rec in r["records"])


def test_every_score_has_reasons(tmp_path):
    r = run(FIX / "messy_crm.csv", demo=True, out_root=tmp_path)
    assert all(rec["reasons"] or rec["unknown"] for rec in r["records"])


def test_score_api_for_inbound_leads():
    c = TestClient(app)
    assert c.post("/score", json={"lead": {"Email": "a@b.example"}, "icp_path": "nope.yaml"}).status_code == 400
    out = c.post("/score", json={"lead": {"Email": "Anna@Acme.example", "Job Title": "CFO", "Country": "Germany",
                                          "Company": "Acme"}, "icp_path": "fixtures/demo/icp.yaml"}).json()
    assert out["record"]["email"] == "anna@acme.example" and out["record"]["persona"] == "finance"
    assert "industry" in out["unknown"] and out["brief"]


def test_n8n_workflow_is_wired():
    wf = json.loads(Path("n8n/crm-tidy.workflow.json").read_text())
    names = {n["name"] for n in wf["nodes"]}
    for src, conns in wf["connections"].items():
        assert src in names and all(c["node"] in names for branch in conns["main"] for c in branch)
    assert "hooks.slack.com/services/T" not in json.dumps(wf)


def test_paid_provider_refused(monkeypatch):
    monkeypatch.delenv("CRMTIDY_ALLOW_PAID", raising=False)
    with pytest.raises(llm.PaidProviderError):
        llm.check_cost({"id": "anthropic", "paid": True})


def test_api_token_is_enforced_when_set(monkeypatch):
    c = TestClient(app)
    monkeypatch.setenv("CRMTIDY_API_TOKEN", "s3cret-for-tests")
    assert c.get("/healthz").status_code == 401
    assert c.get("/healthz", headers={"X-Api-Token": "s3cret-for-tests"}).status_code == 200
