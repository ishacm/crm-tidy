"""Local API for n8n: score one inbound lead in real time, or run a whole file.

  uvicorn crm_tidy.serve:app --port 8091
  POST /score   {"lead": {...}, "icp_path": "icp.yaml"}   -> cleaned record, fit score, tier, owner, brief
  POST /run     {"csv_path": "...", "icp_path": "icp.yaml"}
Localhost only by default. If n8n runs in Docker, start it with --host 0.0.0.0 AND set CRMTIDY_API_TOKEN.
"""
import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from crm_tidy import ROOT, clean, icp as icp_mod, ingest, route, score
from crm_tidy.run import run

def require_token(x_api_token: str | None = Header(default=None)):
    """If CRMTIDY_API_TOKEN is set, every call must send it as the X-Api-Token header. Set it whenever the API listens
    beyond localhost (for example --host 0.0.0.0 so n8n in Docker can reach it)."""
    want = os.environ.get("CRMTIDY_API_TOKEN")
    if want and not hmac.compare_digest(x_api_token or "", want):
        raise HTTPException(status_code=401, detail="missing or wrong X-Api-Token")


app = FastAPI(title="crm-tidy", dependencies=[Depends(require_token)])
DEFAULT_ICP = ROOT / "icp.yaml"   # your reviewed ICP; the demo ICP is never used silently


class ScoreIn(BaseModel):
    lead: dict
    icp_path: str | None = None


class RunIn(BaseModel):
    csv_path: str
    icp_path: str | None = None
    website: str | None = None


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/score")
def score_lead(body: ScoreIn):
    path = body.icp_path or DEFAULT_ICP
    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail=f"no ICP at {path}: run crm_tidy.run --website ... once, review "
                                                    f"the drafted icp.yaml and copy it to the repo root (or pass icp_path)")
    icp = icp_mod.load(path)
    mapping = ingest.map_columns(list(body.lead))
    rec = {f: "" for f in ingest.FIELDS} | {mapping[k]: str(v) for k, v in body.lead.items() if k in mapping}
    rec["row"], rec["extra"] = 0, {}
    r = clean.clean_record(rec)
    r.update(score.score(r, icp))
    route.assign([r])
    return {"tier": r["tier"], "fit_score": r["fit_score"], "owner": r.get("route_owner"), "reasons": r["reasons"],
            "unknown": r["unknown"], "brief": route.brief(r),
            "record": {k: r[k] for k in ("first_name", "last_name", "email", "title", "persona", "seniority",
                                         "company", "domain", "country", "free_email")}}


@app.post("/run")
def run_file(body: RunIn):
    r = run(body.csv_path, website=body.website, icp_path=body.icp_path)
    return {"summary": r["summary"], "files": r["files"]}
