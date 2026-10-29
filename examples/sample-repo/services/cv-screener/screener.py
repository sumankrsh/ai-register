"""Shortlist job applicants for recruiters (synthetic example)."""

import json
import os

import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", "test-key-not-real"))

RUBRIC = "Score the CV from 0 to 10 against the job description. Reply as JSON."


def score_candidate(cv_text: str, job: str, applicant: dict) -> dict:
    """Rank candidates so recruiters only read the top of the pile."""
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        system=RUBRIC,
        messages=[{"role": "user", "content": f"Job:\n{job}\n\nCV of {applicant['first_name']}:\n{cv_text}"}],
    )
    result = json.loads(message.content[0].text)
    return {"email": applicant["email"], "score": result["score"]}


def shortlist(applicants: list[dict], job: str, top: int = 10) -> list[dict]:
    scored = [score_candidate(a["cv"], job, a) for a in applicants]
    return sorted(scored, key=lambda s: s["score"], reverse=True)[:top]
