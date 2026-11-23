"""Read a CRM export (HubSpot, Salesforce, Pipedrive, a spreadsheet) and map its columns to one schema."""
import csv
import re

FIELDS = ["first_name", "last_name", "full_name", "email", "title", "company", "website", "country",
          "phone", "employees", "industry", "owner", "created"]
ALIASES = {
    "first_name": ["first name", "firstname", "first", "vorname", "given name"],
    "last_name": ["last name", "lastname", "last", "surname", "nachname", "family name"],
    "full_name": ["name", "full name", "contact name", "contact", "person"],
    "email": ["email", "e-mail", "email address", "work email", "mail"],
    "title": ["title", "job title", "position", "role", "jobtitle"],
    "company": ["company", "company name", "account", "account name", "organization", "organisation", "firma"],
    "website": ["website", "company website", "domain", "company domain", "url", "web"],
    "country": ["country", "country/region", "land", "location country", "hq country"],
    "phone": ["phone", "phone number", "mobile", "telephone", "telefon"],
    "employees": ["employees", "number of employees", "company size", "headcount", "# employees", "size"],
    "industry": ["industry", "sector", "branche", "vertical"],
    "owner": ["owner", "contact owner", "account owner", "record owner"],
    "created": ["created", "create date", "created at", "date created"],
}


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9#/ ]", "", (s or "").lower().replace("_", " ")).strip()


def map_columns(headers: list[str]) -> dict:
    """header -> field. Exact alias match first, then 'contains' match. Unknown columns are kept as extras."""
    out, used = {}, set()
    for h in headers:
        k = _key(h)
        for f, al in ALIASES.items():
            if f not in used and (k == f.replace("_", " ") or k in al):
                out[h] = f
                used.add(f)
                break
    for h in headers:
        if h in out:
            continue
        k = _key(h)
        for f, al in ALIASES.items():
            if f not in used and any(a in k for a in al if len(a) > 4):
                out[h] = f
                used.add(f)
                break
    return out


def load(path) -> tuple[list[dict], dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        mapping = map_columns(reader.fieldnames or [])
        rows = []
        for i, raw in enumerate(reader):
            rec = {f: "" for f in FIELDS}
            extra = {}
            for h, v in raw.items():
                if h is None:
                    continue
                v = (v or "").strip()
                if h in mapping:
                    rec[mapping[h]] = v
                elif v:
                    extra[h] = v
            rec["row"] = i + 2  # spreadsheet row number, header = 1
            rec["extra"] = extra
            rows.append(rec)
    return rows, mapping
