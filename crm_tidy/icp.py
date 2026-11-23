"""Draft an ICP from a website (or load the one you edited). Stored as icp.yaml so it is easy to review."""
from pathlib import Path

import yaml

from crm_tidy import ROOT, web
from crm_tidy.llm import complete_json

PROMPT = (ROOT / "prompts" / "icp.md").read_text()


def draft(url: str, html: str | None = None) -> dict:
    raw = html if html is not None else web.get(url)
    if not raw:
        raise RuntimeError(f"could not load {url}")
    text = web.html_to_text(raw, 6000)
    icp = complete_json(PROMPT.replace("{url}", url).replace("{text}", text), "icp", context={"url": url, "text": text})
    icp["source_url"] = url
    icp["status"] = "draft: review before trusting the scores"
    return icp


def load(path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def save(icp: dict, path) -> None:
    Path(path).write_text(yaml.safe_dump(icp, sort_keys=False, allow_unicode=True))
