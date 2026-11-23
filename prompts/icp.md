You are a GTM strategist. Read this company's homepage and draft its ideal customer profile (ICP).
Return JSON only:
{"company": "...", "sells": "what it sells, max 15 words",
 "industries": ["3-6 target industries, short lowercase labels like 'software', 'e-commerce', 'agencies'"],
 "employees": {"min": 0, "max": 0},
 "geos": ["ISO-2 country codes it clearly serves, or [] if global"],
 "personas": ["2-4 of: finance, founder_exec, operations, technical, marketing, sales, people, procurement"],
 "seniority": ["1-3 of: c_level, vp_director, manager, ic"],
 "disqualifiers": ["short phrases, e.g. 'fewer than 10 employees', 'competitor'"],
 "competitor_domains": ["domains of obvious competitors, if named on the page"]}
Be conservative: only what the page supports. The user will edit this file.

HOMEPAGE ({url}):
{text}
