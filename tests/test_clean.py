from crm_tidy import clean, ingest


def test_column_mapping_handles_common_exports():
    hubspot = ingest.map_columns(["First Name", "Last Name", "Email", "Job Title", "Company Name", "Website URL",
                                  "Country/Region", "Number of Employees", "Contact owner"])
    assert hubspot["Email"] == "email" and hubspot["Company Name"] == "company" and hubspot["Website URL"] == "website"
    assert hubspot["Country/Region"] == "country" and hubspot["Number of Employees"] == "employees"
    sf = ingest.map_columns(["Name", "Title", "Account Name", "Mailing Country", "Phone"])
    assert sf["Name"] == "full_name" and sf["Account Name"] == "company" and sf["Title"] == "title"


def test_semicolon_csv_is_read(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Vorname;Nachname;E-Mail;Firma\nAnna;Schmidt;anna@acme.example;Acme GmbH\n")
    rows, mapping = ingest.load(p)
    assert rows[0]["first_name"] == "Anna" and rows[0]["company"] == "Acme GmbH" and rows[0]["email"] == "anna@acme.example"


def test_domain_country_phone_size():
    assert clean.domain_of("https://www.Acme.example/about") == "acme.example"
    assert clean.domain_of("", "bob@gmail.com") == "" and clean.domain_of("", "bob@acme.example") == "acme.example"
    assert clean.norm_country("United States") == "US" and clean.norm_country("deutschland") == "DE"
    assert clean.norm_phone("0049 (30) 555-0101") == "+49305550101" and clean.norm_phone("555") == ""
    assert clean.employees("51-200") == 125 and clean.employees("1,200") == 1200 and clean.employees("") is None


def test_titles_map_to_persona_and_seniority():
    assert clean.persona("Head of Finance") == ("finance", "vp_director")
    assert clean.persona("Founder & CEO") == ("founder_exec", "c_level")
    assert clean.persona("Working Student Finance") == ("finance", "intern")
    assert clean.persona("Senior Accountant") == ("finance", "manager")
    assert clean.persona("") == ("", "")


def _rec(**kw):
    base = {f: "" for f in ingest.FIELDS} | {"row": kw.pop("row", 2), "extra": {}}
    return clean.clean_record(base | kw)


def test_dedupe_by_email_case_and_by_name_at_company():
    a = _rec(row=2, first_name="anna", last_name="SCHMIDT", email="Anna.Schmidt@Acme.example", website="acme.example", title="CFO")
    b = _rec(row=3, first_name="Anna", last_name="Schmidt", email="anna.schmidt@acme.example", phone="+49 170 1234567")
    c = _rec(row=4, first_name="Anna", last_name="Schmidt", company="ACME GmbH")
    a["company"] = "Acme GmbH"; a["company_key"] = clean.norm_company("Acme GmbH")
    out, log = clean.dedupe([a, b, c])
    assert len(out) == 1 and sorted(out[0]["merged_rows"]) == [2, 3, 4]
    assert out[0]["phone"] == "+491701234567" and out[0]["title"] == "CFO"


def test_invalid_and_personal_emails_are_flagged():
    assert _rec(email="jane.doe@")["email_status"] == "invalid"
    assert _rec(email="bob@gmail.com")["free_email"] is True


def test_one_spelling_per_company():
    recs = [_rec(row=i, company=n, website="orbit.example") for i, n in enumerate(["ORBIT DEVTOOLS", "Orbit Devtools", "Orbit Devtools"])]
    assert clean.canonical_companies(recs) == 1 and {r["company"] for r in recs} == {"Orbit Devtools"}
