from ai_register.risk import assess


def line(text, file="app.py", n=1):
    return [(file, n, text)]


def test_default_is_minimal_with_honest_reasoning():
    result = assess(line("def add(a, b): return a + b"))
    assert result.tier == "minimal-risk"
    assert any("not a conclusion" in r for r in result.reasoning)
    assert any("purpose field is empty" in r for r in result.reasoning)


def test_recruitment_is_high_risk_and_cites_location():
    result = assess(line("def rank_candidates(cvs):", "hr/screen.py", 12))
    assert result.tier == "high-risk-candidate"
    assert "Annex III 4" in result.reasoning[0]
    assert "hr/screen.py:12" in result.reasoning[0]


def test_credit_and_life_insurance():
    assert assess(line("compute credit_score for applicant")).tier == "high-risk-candidate"
    assert assess(line("life insurance underwriting model")).tier == "high-risk-candidate"
    # Property insurance is not an Annex III use case.
    assert assess(line("motor insurance claims summary")).tier == "minimal-risk"


def test_chatbot_is_limited_risk():
    assert assess(line("You are a helpful customer support assistant chatbot")).tier == "limited-risk"


def test_prohibited_beats_everything_and_is_listed_first():
    lines = [("a.py", 1, "chatbot"), ("b.py", 2, "social_scoring = True"), ("c.py", 3, "credit_score")]
    result = assess(lines)
    assert result.tier == "prohibited-candidate"
    assert result.reasoning[0].startswith("Art. 5(1)(c)")
    assert len(result.reasoning) == 3


def test_purpose_field_counts():
    result = assess(line("x = 1"), purpose="Shortlist job applicants for the recruiting team")
    assert result.tier == "high-risk-candidate"
    assert "purpose (register)" in result.reasoning[0]


def test_examples_are_capped():
    lines = [("a.py", n, "chatbot") for n in range(1, 20)]
    assert assess(lines).reasoning[0].count('"chatbot" at') == 3
