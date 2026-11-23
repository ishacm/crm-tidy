#!/usr/bin/env python3
"""Generate the fictional, deliberately messy CRM used by the demo and tests. Deterministic (fixed seed).
Every company uses a .example domain, so no real company or person is involved."""
import csv
import json
import random
from pathlib import Path

random.seed(7)
OUT = Path(__file__).resolve().parent.parent / "fixtures" / "demo"
COMPANIES = [  # name, domain, industry words on the homepage, employees, country variants
    ("Brightpath Software GmbH", "brightpath.example", "B2B software platform for logistics teams", 120, ["Germany", "DE", "deutschland"]),
    ("Nordlicht Commerce", "nordlicht.example", "online store and e-commerce brand for outdoor gear", 65, ["Germany", "germany"]),
    ("Canal Street Studio", "canalstreet.example", "creative agency for brands", 28, ["UK", "United Kingdom"]),
    ("Tulip Data B.V.", "tulipdata.example", "data analytics software for retailers", 90, ["Netherlands", "NL", "holland"]),
    ("Harbor Freight Labs Inc", "harborlabs.example", "SaaS for freight forwarders", 210, ["USA", "United States", "US"]),
    ("Maple & Co Consulting", "mapleco.example", "management consulting firm", 45, ["Canada", "CA"]),
    ("Kestrel Robotics", "kestrel.example", "industrial robots and manufacturing automation", 400, ["Germany", "DE"]),
    ("Lumen Health", "lumenhealth.example", "digital health app for clinics", 150, ["USA", "U.S."]),
    ("Pinecone Goods", "pinecone.example", "e-commerce shop for home goods", 35, ["UK", "england"]),
    ("Riverbend Agency", "riverbend.example", "performance marketing agency", 22, ["Ireland", "IE"]),
    ("Atlas Payroll Ltd", "atlaspayroll.example", "payroll software for small businesses", 75, ["UK", "GB"]),
    ("Sunday Foundation", "sundayfoundation.example", "nonprofit foundation supporting education", 18, ["USA"]),
    ("Quarry Analytics SAS", "quarry.example", "analytics software for construction companies", 60, ["France", "FR"]),
    ("Juniper Travel", "junipertravel.example", "online travel booking marketplace", 300, ["Spain", "ES"]),
    ("Northbook", "northbook.example", "expense management for small teams", 80, ["USA"]),  # a competitor
    ("Orbit Devtools", "orbitdev.example", "developer tools and API platform", 55, ["USA", "US"]),
    ("Fjord Furniture AB", "fjord.example", "furniture manufacturer", 500, ["Sweden", "SE"]),
    ("Saffron Kitchens", "saffron.example", "restaurant group", 140, ["India", "IN"]),
    ("Vela Security", "velasec.example", "cybersecurity software for mid-sized companies", 110, ["Netherlands"]),
    ("Tiny Ink", "tinyink.example", "stationery online shop run by two founders", 3, ["Germany"]),
]
PEOPLE = [("Anna", "Schmidt"), ("Tom", "Becker"), ("Priya", "Nair"), ("James", "Okafor"), ("Lena", "Vogel"),
          ("Sofia", "Rossi"), ("Daan", "de Vries"), ("Emma", "Clarke"), ("Lucas", "Martin"), ("Mia", "Hoffmann"),
          ("Noah", "Fischer"), ("Chloe", "Dubois"), ("Arjun", "Mehta"), ("Olivia", "Brown"), ("Felix", "Wagner"),
          ("Hannah", "Lee"), ("Mateo", "García"), ("Ella", "Johansson"), ("Ben", "Taylor"), ("Zoe", "Müller")]
TITLES = ["CFO", "Head of Finance", "Finance Manager", "Controller", "Founder & CEO", "COO", "Office Manager",
          "Head of Operations", "Senior Accountant", "VP Engineering", "Marketing Manager", "Account Executive",
          "Working Student Finance", "HR Business Partner", "Procurement Lead", "Co-Founder", "Bookkeeper", ""]
SIZES = lambda n: random.choice([str(n), f"{max(1, n - 20)}-{n + 30}", "", f"{n:,}" if n > 999 else str(n)])


def messy_name(s):
    return random.choice([s, s, s.lower(), s.upper(), f" {s} "])


rows, homepages = [], {}
for name, dom, desc, emp, countries in COMPANIES:
    homepages[dom] = (f"<html><head><title>{name}</title></head><body><h1>{name}</h1><p>We are a {desc}."
                      + (f" Our team of {emp} people" if random.random() < 0.3 else "") + "</p></body></html>")
    for _ in range(random.randint(2, 4)):
        fn, ln = random.choice(PEOPLE)
        email = f"{fn.lower()}.{ln.lower().replace(' ', '')}@{dom}".replace("ü", "ue").replace("í", "i")
        r = {"First Name": messy_name(fn), "Last Name": messy_name(ln), "Email": email,
             "Job Title": random.choice(TITLES), "Company": name if random.random() > 0.1 else name.upper(),
             "Website": random.choice([f"https://www.{dom}/", dom, f"http://{dom}", ""]),
             "Country": random.choice(countries), "Phone": random.choice(["", "+49 89 1234567", "0049 (30) 555-0101", "555"]),
             "Number of Employees": SIZES(emp), "Industry": "", "Contact Owner": random.choice(["", "", "Sam"])}
        rows.append(r)
# deliberate problems
dup = dict(rows[0]); dup["Email"] = dup["Email"].upper(); dup["Phone"] = "+49 170 9998887"; dup["Job Title"] = ""; rows.append(dup)
dup2 = dict(rows[5]); dup2["Email"] = ""; dup2["Website"] = ""; rows.append(dup2)
rows.append({**rows[3], "Email": rows[3]["Email"].replace("@", " @ ")})
rows.append({"First Name": "jane", "Last Name": "DOE", "Email": "jane.doe@", "Job Title": "CFO", "Company": "",
             "Website": "", "Country": "usa", "Phone": "", "Number of Employees": "", "Industry": "", "Contact Owner": ""})
rows.append({"First Name": "Marco", "Last Name": "Bianchi", "Email": "marco.bianchi1987@gmail.com", "Job Title": "Freelance Bookkeeper",
             "Company": "", "Website": "", "Country": "Italy", "Phone": "", "Number of Employees": "", "Industry": "", "Contact Owner": ""})
rows.append({"First Name": "Sara", "Last Name": "Kim", "Email": "sara@vela-sec.example", "Job Title": "Head of Finance",
             "Company": "Vela Security B.V.", "Website": "velasec.example", "Country": "NL", "Phone": "",
             "Number of Employees": "101-250", "Industry": "Computer & Network Security", "Contact Owner": ""})
random.shuffle(rows)
with open(OUT / "messy_crm.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
(OUT / "homepages.json").write_text(json.dumps(homepages, indent=1))
print(len(rows), "rows,", len(homepages), "companies")
