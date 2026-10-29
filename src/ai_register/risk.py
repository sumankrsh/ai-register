"""Draft EU AI Act risk tiers.

This is keyword screening, not legal analysis. It looks for words in the code,
prompts and the human-written purpose of a system that suggest a use case
named in the EU AI Act, and shows exactly which words it found and where.
A person must confirm or change the tier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TIERS = ("prohibited-candidate", "high-risk-candidate", "limited-risk", "minimal-risk")
TIER_RANK = {tier: rank for rank, tier in enumerate(TIERS)}


@dataclass(frozen=True)
class UseCase:
    tier: str
    reference: str
    label: str
    pattern: re.Pattern[str]


def _u(tier: str, reference: str, label: str, regex: str) -> UseCase:
    return UseCase(tier, reference, label, re.compile(regex, re.IGNORECASE))


USE_CASES: list[UseCase] = [
    _u(
        "prohibited-candidate",
        "Art. 5(1)(c)",
        "social scoring",
        r"\bsocial[_\s-]?scor(e|ing)\b|\bcitizen[_\s-]?score\b|\btrustworthiness[_\s-]?score\b",
    ),
    _u(
        "prohibited-candidate",
        "Art. 5(1)(f)",
        "emotion recognition at work or in education",
        r"\b(employee|worker|staff|student|pupil)[_\s-]?(emotion|mood|sentiment)[_\s-]?(recognition|detection|monitor\w*)\b",
    ),
    _u(
        "prohibited-candidate",
        "Art. 5(1)(e)",
        "untargeted scraping of facial images",
        r"\b(scrape|scraping|crawl)\w*[_\s-]?(face|facial)[_\s-]?images?\b|\bface[_\s-]?scrap\w*",
    ),
    _u(
        "prohibited-candidate",
        "Art. 5(1)(d)",
        "predicting crime from profiling",
        r"\b(crime|criminal|offen[cs]e)[_\s-]?(risk[_\s-]?)?predict\w*|\bpredictive[_\s-]?policing\b",
    ),
    _u(
        "high-risk-candidate",
        "Annex III 1",
        "biometric identification or categorisation",
        r"\bface[_\s-]?(recognition|match\w*|verification|embedding)\b|\bbiometric\w*|\bfingerprint[_\s-]?match\w*",
    ),
    _u(
        "high-risk-candidate",
        "Annex III 2",
        "safety component of critical infrastructure",
        r"\b(power|electricity|water|gas)[_\s-]?grid\b|\bscada\b|\btraffic[_\s-]?control\b",
    ),
    _u(
        "high-risk-candidate",
        "Annex III 3",
        "education: admission, assessment or proctoring",
        r"\b(exam|essay|student)[_\s-]?(grading|scoring|marking)\b|\badmissions?[_\s-]?(decision|screen\w*|scor\w*)\b|\bproctor\w*",
    ),
    _u(
        "high-risk-candidate",
        "Annex III 4",
        "employment: recruitment, screening or worker management",
        r"\b(cv|resume|résumé|candidate|applicant|job[_\s-]?application)s?[_\s-]?(screen\w*|rank\w*|scor\w*|shortlist\w*|filter\w*)"
        r"|\b(screen|rank|score|shortlist)\w*[_\s-]?(the[_\s-]|job[_\s-])?(cvs?|resumes?|candidates?|applicants?)\b"
        r"|\b(hiring|recruitment)[_\s-]?decision\w*|\bpromotion[_\s-]?decision\w*|\btermination[_\s-]?decision\w*",
    ),
    _u(
        "high-risk-candidate",
        "Annex III 5(b)",
        "creditworthiness or credit scoring",
        r"\bcredit[_\s-]?(score|scoring|worthiness|decision\w*|limit[_\s-]?decision\w*)\b|\bcreditworth\w*|\bloan[_\s-]?(approval|decision\w*|eligibility)\b",
    ),
    _u(
        "high-risk-candidate",
        "Annex III 5(c)",
        "risk assessment and pricing for life or health insurance",
        r"\b(life|health)[_\s-]?(insurance[_\s-]?)?(underwriting|premium[_\s-]?pricing|risk[_\s-]?pricing)\b",
    ),
    _u(
        "high-risk-candidate",
        "Annex III 5(a)",
        "eligibility for public benefits or services",
        r"\b(benefit|welfare|social[_\s-]?security)[_\s-]?(eligibility|entitlement)\b",
    ),
    _u(
        "high-risk-candidate",
        "Annex III 5(d)",
        "triage of emergency calls",
        r"\bemergency[_\s-]?(call|dispatch)[_\s-]?(triage|priorit\w*)\b",
    ),
    _u(
        "limited-risk",
        "Art. 50(1)",
        "chatbot or assistant that talks to people",
        r"\b(chat[_\s-]?bot|virtual[_\s-]?assistant|customer[_\s-]?(support|service)[_\s-]?(bot|agent|assistant)|support[_\s-]?chat|live[_\s-]?chat)\b",
    ),
    _u(
        "limited-risk",
        "Art. 50(2)",
        "generating synthetic images, audio or video",
        r"\b(text[_\s-]?to[_\s-]?(image|speech|video)|image[_\s-]?generation|voice[_\s-]?clon\w*)\b",
    ),
    _u("limited-risk", "Art. 50(4)", "deep fakes", r"\bdeep[_\s-]?fakes?\b"),
    _u("limited-risk", "Art. 50(3)", "emotion recognition", r"\bemotion[_\s-]?(recognition|detection)\b"),
]

MAX_EXAMPLES = 3


@dataclass
class Assessment:
    tier: str
    reasoning: list[str]


def assess(lines: list[tuple[str, int, str]], purpose: str | None = None) -> Assessment:
    """Return the most serious tier any use case matched, with the evidence."""
    sources = list(lines)
    if purpose:
        sources.insert(0, ("purpose (register)", 0, purpose))
    hits: dict[UseCase, list[str]] = {}
    for file, line_no, text in sources:
        for case in USE_CASES:
            match = case.pattern.search(text)
            if not match:
                continue
            where = file if line_no == 0 else f"{file}:{line_no}"
            examples = hits.setdefault(case, [])
            if len(examples) < MAX_EXAMPLES:
                examples.append(f'"{match.group(0)}" at {where}')
    if not hits:
        reasoning = [
            "No wording matched a use case listed in Art. 5, Art. 50 or Annex III.",
            "Minimal risk is the default, not a conclusion: record the system's purpose and review it.",
        ]
        if not purpose:
            reasoning.append("The purpose field is empty, so only code and prompts were checked.")
        return Assessment("minimal-risk", reasoning)
    ordered = sorted(hits.items(), key=lambda item: (TIER_RANK[item[0].tier], item[0].reference))
    tier = ordered[0][0].tier
    reasoning = [
        f"{case.reference} ({case.label}) -> {case.tier}: matched {', '.join(examples)}" for case, examples in ordered
    ]
    return Assessment(tier, reasoning)
