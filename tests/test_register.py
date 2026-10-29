from datetime import UTC, datetime

import yaml

from ai_register.diff import compare
from ai_register.register import build, dump, effective_tier, load, save
from ai_register.scanner import scan

from .conftest import write

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def systems_by_id(register):
    return {s["id"]: s for s in register["systems"]}


def test_register_shape(sample_repo):
    register = build(scan(sample_repo), "sample-repo", now=NOW)
    assert register["register_version"] == 1
    assert register["generated_at"] == "2026-01-01T00:00:00+00:00"
    assert "DRAFT" in register["notice"]
    cv = systems_by_id(register)["services/cv-screener"]
    assert cv["risk"]["draft_tier"] == "high-risk-candidate"
    assert cv["owner"] is None and cv["review_status"] == "draft"
    control_ids = [c["id"] for c in cv["controls"]]
    assert {"A.3.2", "A.5.4", "A.6.2.2", "A.10.3"} <= set(control_ids)
    assert control_ids == sorted(control_ids, key=lambda c: [int(p) for p in c[2:].split(".")])


def test_human_fields_survive_a_rescan(sample_repo, tmp_path):
    first = build(scan(sample_repo), "sample-repo", now=NOW)
    chatbot = systems_by_id(first)["services/support-chatbot"]
    chatbot["owner"] = "Customer Ops (test owner)"
    chatbot["purpose"] = "Answers parcel tracking questions"
    chatbot["risk"]["reviewed_tier"] = "limited-risk"
    chatbot["risk"]["reviewer_notes"] = "Disclosure banner in place"
    chatbot["controls"][0]["status"] = "done"
    chatbot["controls"][0]["evidence"] = "RACI v2"
    path = tmp_path / "ai-register.yaml"
    save(first, path)

    second = build(scan(sample_repo), "sample-repo", previous=load(path), now=NOW)
    again = systems_by_id(second)["services/support-chatbot"]
    assert again["owner"] == "Customer Ops (test owner)"
    assert again["purpose"] == "Answers parcel tracking questions"
    assert again["risk"]["reviewed_tier"] == "limited-risk"
    assert again["risk"]["reviewer_notes"] == "Disclosure banner in place"
    assert again["controls"][0]["status"] == "done"
    assert again["controls"][0]["evidence"] == "RACI v2"


def test_purpose_written_by_a_person_changes_the_draft_tier(sample_repo):
    first = build(scan(sample_repo), "sample-repo", now=NOW)
    churn = systems_by_id(first)["ml/churn-model"]
    assert churn["risk"]["draft_tier"] == "minimal-risk"
    churn["purpose"] = "Feeds credit limit decisions for retail customers"
    second = build(scan(sample_repo), "sample-repo", previous=first, now=NOW)
    assert systems_by_id(second)["ml/churn-model"]["risk"]["draft_tier"] == "high-risk-candidate"


def test_reviewed_tier_wins(sample_repo):
    register = build(scan(sample_repo), "sample-repo", now=NOW)
    entry = systems_by_id(register)["services/cv-screener"]
    assert effective_tier(entry) == "high-risk-candidate"
    entry["risk"]["reviewed_tier"] = "limited-risk"
    assert effective_tier(entry) == "limited-risk"


def test_removed_system_is_kept_as_not_detected(sample_repo):
    first = build(scan(sample_repo), "sample-repo", now=NOW)
    (sample_repo / "services" / "cv-screener" / "screener.py").unlink()
    second = build(scan(sample_repo), "sample-repo", previous=first, now=NOW)
    cv = systems_by_id(second)["services/cv-screener"]
    assert cv["lifecycle"] == "not-detected"
    assert cv["findings"]  # last known evidence stays for the auditor


def test_yaml_round_trip_and_rejects_other_files(sample_repo, tmp_path):
    register = build(scan(sample_repo), "sample-repo", now=NOW)
    assert yaml.safe_load(dump(register)) == register
    bad = tmp_path / "other.yaml"
    bad.write_text("name: something else\n")
    try:
        load(bad)
    except ValueError as exc:
        assert "not an ai-register file" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_diff_reports_new_provider_model_and_tier(sample_repo):
    old = build(scan(sample_repo), "sample-repo", now=NOW)
    write(
        sample_repo,
        "services/doc-search/src/rank.ts",
        'import OpenAI from "openai";\n// rank candidates for hiring\n'
        'const r = await client.responses.create({ model: "gpt-4.1" });\n',
    )
    write(sample_repo, "services/new-agent/requirements.txt", "anthropic\n")
    write(sample_repo, "services/new-agent/agent.py", "import anthropic\n")
    new = build(scan(sample_repo), "sample-repo", previous=old, now=NOW)
    result = compare(old, new)
    statuses = {c.id: c.status for c in result.changes}
    assert statuses == {"services/doc-search": "changed", "services/new-agent": "added"}
    details = next(c for c in result.changes if c.id == "services/doc-search").details
    assert "provider added: openai" in details
    assert "model added: gpt-4.1" in details
    assert "risk tier: minimal-risk -> high-risk-candidate" in details


def test_diff_ignores_line_shifts(sample_repo):
    old = build(scan(sample_repo), "sample-repo", now=NOW)
    app = sample_repo / "services" / "support-chatbot" / "app.py"
    app.write_text("\n\n\n" + app.read_text())
    new = build(scan(sample_repo), "sample-repo", previous=old, now=NOW)
    assert compare(old, new).empty
