Classify each company from its homepage text. Return JSON only:
{"items": [{"domain": "...", "industry": "short lowercase label", "b2b": true, "description": "max 15 words",
            "employees_hint": null}]}
industry: prefer one of: {industries}; otherwise a short label. employees_hint: a number ONLY if the page states it.
If the text is empty or unclear, use industry "unknown".

COMPANIES:
{companies}
