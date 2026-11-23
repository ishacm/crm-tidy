"""Normalise fields, map titles to personas, and merge duplicates. Rules first, so it is fast, free and explainable."""
import re
import unicodedata

FREE_MAIL = {"gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", "icloud.com",
             "me.com", "aol.com", "gmx.de", "gmx.net", "web.de", "t-online.de", "proton.me", "protonmail.com", "mail.com"}
SUFFIXES = r"\b(gmbh|ag|se|kg|ug|inc|llc|ltd|limited|plc|bv|b\.v\.|sas|sarl|srl|oy|ab|as|co|corp|corporation|company)\b\.?"
COUNTRIES = {
    "US": ["us", "usa", "united states", "united states of america", "u.s.", "u.s.a."],
    "GB": ["uk", "gb", "united kingdom", "great britain", "england", "scotland"],
    "DE": ["de", "germany", "deutschland"], "AT": ["at", "austria", "österreich"], "CH": ["ch", "switzerland", "schweiz"],
    "FR": ["fr", "france"], "NL": ["nl", "netherlands", "the netherlands", "holland"], "ES": ["es", "spain", "españa"],
    "IT": ["it", "italy", "italia"], "CA": ["ca", "canada"], "IE": ["ie", "ireland"], "SE": ["se", "sweden"],
    "DK": ["dk", "denmark"], "IN": ["in", "india"], "AU": ["au", "australia"], "SG": ["sg", "singapore"],
    "PL": ["pl", "poland"], "BE": ["be", "belgium"], "PT": ["pt", "portugal"], "FI": ["fi", "finland"], "NO": ["no", "norway"],
}
COUNTRY_LOOKUP = {alias: iso for iso, al in COUNTRIES.items() for alias in al}
# persona: (pattern, persona). Checked in order; first match wins.
PERSONAS = [
    (r"\b(cfo|chief financial|finance|financial|controller|controlling|accounting|accountant|bookkeep|treasur|fp&a|payroll)\b", "finance"),
    (r"\b(ceo|founder|co-founder|cofounder|owner|managing director|geschäftsführer|president|general manager)\b", "founder_exec"),
    (r"\b(coo|operations|ops|office manager|chief of staff|people ops)\b", "operations"),
    (r"\b(cto|engineer|developer|software|devops|it |it$|infrastructure|architect|data)\b", "technical"),
    (r"\b(cmo|marketing|growth|demand gen|brand|content|seo)\b", "marketing"),
    (r"\b(cro|sales|account executive|business development|bdr|sdr|revenue|partnerships)\b", "sales"),
    (r"\b(hr|human resources|talent|recruit|people)\b", "people"),
    (r"\b(procurement|purchasing|buyer|einkauf)\b", "procurement"),
]
SENIORITY = [
    (r"\b(chief|c[efotrm]o|founder|co-founder|owner|president|managing director|geschäftsführer)\b", "c_level"),
    (r"\b(vp|vice president|head of|director|leiter|leitung)\b", "vp_director"),
    (r"\b(manager|lead|teamlead|team lead|principal|senior)\b", "manager"),
    (r"\b(intern|student|werkstudent|trainee|working student|apprentice)\b", "intern"),
]
EMAIL_RE = re.compile(r"^[a-z0-9._%+'-]+@[a-z0-9.-]+\.[a-z]{2,}$")


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()


def norm_company(name: str) -> str:
    n = ascii_fold(name).lower()
    n = re.sub(SUFFIXES, " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def domain_of(website: str = "", email: str = "") -> str:
    w = (website or "").strip().lower()
    if w:
        w = re.sub(r"^https?://", "", w).split("/")[0].split("?")[0]
        w = re.sub(r"^www\.", "", w).strip(".")
        if "." in w:
            return w
    if "@" in (email or ""):
        d = email.split("@")[-1].lower().strip(".")
        if d and d not in FREE_MAIL:
            return d
    return ""


def norm_country(c: str) -> str:
    c = (c or "").strip().lower().rstrip(".")
    return COUNTRY_LOOKUP.get(c, c.upper() if len(c) == 2 else "")


def norm_phone(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    digits = re.sub(r"[^\d+]", "", p)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    return digits if len(re.sub(r"\D", "", digits)) >= 7 else ""


def title_case(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s:
        return ""
    if s.isupper() or s.islower():
        return " ".join(w if w.lower() in ("van", "von", "de", "der", "da") else w[:1].upper() + w[1:].lower() for w in s.split(" "))
    return s


def employees(v: str) -> int | None:
    """'51-200' -> 125 (midpoint), '1,200' -> 1200, '' -> None."""
    v = (v or "").replace(",", "").replace(".", "").strip().lower()
    m = re.match(r"^(\d+)\s*[-–to]+\s*(\d+)", v)
    if m:
        return (int(m.group(1)) + int(m.group(2))) // 2
    m = re.match(r"^(\d+)\+?", v)
    return int(m.group(1)) if m else None


def persona(title: str) -> tuple[str, str]:
    t = " " + ascii_fold(title).lower() + " "
    p = next((name for pat, name in PERSONAS if re.search(pat, t)), "unknown" if title.strip() else "")
    s = next((name for pat, name in SENIORITY if re.search(pat, t)), "ic" if title.strip() else "")
    return p, s


def clean_record(r: dict) -> dict:
    c = dict(r)
    issues = []
    if not c.get("first_name") and c.get("full_name"):
        parts = c["full_name"].split()
        c["first_name"], c["last_name"] = parts[0], " ".join(parts[1:])
    c["first_name"], c["last_name"] = title_case(c.get("first_name")), title_case(c.get("last_name"))
    email = (c.get("email") or "").strip().lower().replace(" ", "")
    c["email_status"] = "missing" if not email else ("valid_syntax" if EMAIL_RE.match(email) else "invalid")
    if c["email_status"] == "invalid":
        issues.append("invalid email")
    c["email"] = email
    c["free_email"] = bool(email) and email.split("@")[-1] in FREE_MAIL
    c["domain"] = domain_of(c.get("website"), email if c["email_status"] == "valid_syntax" else "")
    c["company"] = re.sub(r"\s+", " ", (c.get("company") or "").strip())
    c["company_key"] = norm_company(c["company"])
    c["country"] = norm_country(c.get("country"))
    c["phone"] = norm_phone(c.get("phone"))
    c["employees_n"] = employees(c.get("employees"))
    c["title"] = re.sub(r"\s+", " ", (c.get("title") or "").strip())
    c["persona"], c["seniority"] = persona(c["title"])
    if not c["domain"] and not c["company"]:
        issues.append("no company or domain")
    c["issues"] = issues
    return c


FILLED = ["first_name", "last_name", "email", "title", "company", "domain", "country", "phone", "employees_n", "industry", "persona"]


def completeness(r: dict) -> int:
    return sum(1 for f in FILLED if r.get(f) not in ("", None, "unknown"))


def dedupe(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Merge records that are the same person: same email, or same name at the same company/domain.
    Keeps the most complete record and fills its gaps from the others. Returns (records, merge_log)."""
    groups, index = [], {}
    for r in records:
        name = f"{ascii_fold(r.get('first_name')).lower()} {ascii_fold(r.get('last_name')).lower()}".strip()
        keys = []
        if r.get("email") and r["email_status"] == "valid_syntax":
            keys.append("e:" + r["email"])
        for org in {r.get("domain"), r.get("company_key")} - {None, ""}:
            if name:
                keys.append(f"n:{name}|{org}")
        gid = next((index[k] for k in keys if k in index), None)
        if gid is None:
            gid = len(groups)
            groups.append([])
        groups[gid].append(r)
        for k in keys:
            index[k] = gid
    out, log = [], []
    for g in groups:
        g = sorted(g, key=lambda r: -completeness(r))
        keep = dict(g[0])
        for other in g[1:]:
            for f, v in other.items():
                if f in ("row", "extra", "issues"):
                    continue
                if keep.get(f) in ("", None, "unknown") and v not in ("", None, "unknown"):
                    keep[f] = v
        keep["merged_rows"] = [r["row"] for r in g]
        if len(g) > 1:
            log.append({"kept_row": g[0]["row"], "merged_rows": [r["row"] for r in g[1:]],
                        "reason": "same email" if any(r.get("email") == g[0].get("email") and r.get("email") for r in g[1:]) else "same name and company"})
        out.append(keep)
    return out, log


def canonical_companies(records: list[dict]) -> int:
    """One spelling per company: the most common non-shouting variant across its records. Returns # changed."""
    from collections import Counter, defaultdict
    variants = defaultdict(Counter)
    for r in records:
        key = r.get("domain") or r.get("company_key")
        if key and r.get("company"):
            variants[key][r["company"]] += 1
    changed = 0
    for r in records:
        key = r.get("domain") or r.get("company_key")
        if not key or not r.get("company"):
            continue
        options = sorted(variants[key].items(), key=lambda kv: (kv[0].isupper(), -kv[1]))
        best = options[0][0]
        if best.isupper() and len(best) > 4:
            best = title_case(best)
        if best != r["company"]:
            r["company"], changed = best, changed + 1
    return changed


def run(rows: list[dict]) -> dict:
    cleaned = [clean_record(r) for r in rows]
    renamed = canonical_companies(cleaned)
    merged, log = dedupe(cleaned)
    return {"records": merged, "merges": log, "before": [clean_record(r) for r in rows], "companies_renamed": renamed}
