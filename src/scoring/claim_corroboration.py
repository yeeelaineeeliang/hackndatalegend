from __future__ import annotations

import re
from dataclasses import dataclass


# Each theme separates what a facility CLAIMS (trigger terms in capability
# entries) from what would CORROBORATE that claim (operational evidence such
# as equipment, staff, or procedures). A claim repeated across fields without
# operational evidence is "mentioned_only", not corroborated.
@dataclass(frozen=True)
class ClaimTheme:
    theme_id: str
    label: str
    acuity: str  # high | medium
    claim_pattern: re.Pattern
    evidence_pattern: re.Pattern


def _theme(
    theme_id: str, label: str, acuity: str, claim: str, evidence: str
) -> ClaimTheme:
    return ClaimTheme(
        theme_id=theme_id,
        label=label,
        acuity=acuity,
        claim_pattern=re.compile(claim, re.IGNORECASE),
        evidence_pattern=re.compile(evidence, re.IGNORECASE),
    )


CLAIM_THEMES = [
    _theme(
        "critical_care",
        "Critical care / ICU",
        "high",
        r"\b(icu|intensive care|critical care)\b",
        r"\b(ventilators?|ecmo|intensivists?|life[- ]support|"
        r"multipara monitors?|central (?:line|venous)|"
        r"high dependency|hdu|icu beds?)\b",
    ),
    _theme(
        "emergency_trauma",
        "Emergency & trauma",
        "high",
        r"\b(emergency|trauma|casualty)\b",
        r"\b(ambulances?|resuscitat\w+|defibrillators?|triage|"
        r"24 ?[x/] ?7|round[- ]the[- ]clock|"
        r"emergency (?:room|ward|department|care unit))\b",
    ),
    _theme(
        "neonatal",
        "Neonatal / NICU",
        "high",
        r"\b(nicu|neonat\w+|newborn)\b",
        r"\b(incubators?|phototherapy|radiant warmers?|neonatologists?|"
        r"premature|preterm|nicu beds?)\b",
    ),
    _theme(
        "maternity",
        "Maternity & obstetrics",
        "medium",
        r"\b(maternity|obstetric\w*|gyn(?:ae|e)c\w*|childbirth)\b",
        r"\b(labou?r (?:room|ward)|deliver(?:y|ies)|c[- ]sections?|"
        r"c(?:ae|e)sarean|midwi\w+|obstetricians?|gyn(?:ae|e)cologists?)\b",
    ),
    _theme(
        "oncology",
        "Oncology",
        "medium",
        r"\b(oncolog\w+|cancer)\b",
        r"\b(chemotherapy|radiotherapy|radiation therapy|linear accelerators?|"
        r"brachytherapy|oncologists?|tumou?r boards?)\b",
    ),
    _theme(
        "cardiac",
        "Cardiac care",
        "medium",
        r"\b(cardiac|cardiolog\w+|cardiovascular)\b",
        r"\b(cath labs?|catheterizations?|angiograph\w+|angioplast\w+|"
        r"pacemakers?|cardiologists?|bypass|cabg|echocardiogra\w+)\b",
    ),
    _theme(
        "dialysis_renal",
        "Renal & dialysis",
        "medium",
        r"\b(dialysis|nephrolog\w+|renal|kidney)\b",
        r"\b((?:hemo|haemo)dialysis|dialysis (?:machines?|units?|beds?)|"
        r"nephrologists?|transplants?)\b",
    ),
    _theme(
        "surgery",
        "Surgery",
        "medium",
        r"\b(surger\w+|surgical)\b",
        r"\b(operat(?:ion|ing) theatres?|operating rooms?|"
        r"an(?:ae|e)sthes\w+|surgeons?|laparoscop\w+)\b",
    ),
]

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
SNIPPET_LIMIT = 300


def _matching_snippet(pattern: re.Pattern, text: str) -> str | None:
    if not pattern.search(text):
        return None
    for sentence in SENTENCE_SPLIT.split(text):
        if pattern.search(sentence):
            return sentence.strip()[:SNIPPET_LIMIT]
    return text.strip()[:SNIPPET_LIMIT]


def assess_claim_corroboration(
    capability_claims: list[str],
    description: str,
    procedure_claims: list[str],
    equipment_claims: list[str],
) -> list[dict]:
    """Assess every high-acuity theme claimed in capability entries.

    Returns one assessment per claimed theme:
      support_level:
        corroborated   - operational evidence terms found in any field
        mentioned_only - claim terms repeat in another field, but no
                         operational evidence exists anywhere
        unsupported    - nothing outside the capability entry supports it
      evidence_field / evidence_snippet carry the exact receipt.
    """
    capability_text = " ".join(capability_claims)
    search_fields = [
        ("equipment", " ".join(equipment_claims)),
        ("procedure", " ".join(procedure_claims)),
        ("description", description or ""),
    ]
    assessments = []
    for theme in CLAIM_THEMES:
        claim_match = theme.claim_pattern.search(capability_text)
        if not claim_match:
            continue
        claimed_entry = next(
            (
                claim.strip()[:SNIPPET_LIMIT]
                for claim in capability_claims
                if theme.claim_pattern.search(claim)
            ),
            claim_match.group(0),
        )
        support_level = "unsupported"
        evidence_field = None
        evidence_snippet = None
        for field_name, text in search_fields:
            if not text:
                continue
            snippet = _matching_snippet(theme.evidence_pattern, text)
            if snippet:
                support_level = "corroborated"
                evidence_field = field_name
                evidence_snippet = snippet
                break
        if support_level == "unsupported":
            for field_name, text in search_fields:
                if not text:
                    continue
                snippet = _matching_snippet(theme.claim_pattern, text)
                if snippet:
                    support_level = "mentioned_only"
                    evidence_field = field_name
                    evidence_snippet = snippet
                    break
        assessments.append(
            {
                "theme_id": theme.theme_id,
                "theme_label": theme.label,
                "acuity": theme.acuity,
                "claimed_entry": claimed_entry,
                "support_level": support_level,
                "evidence_field": evidence_field,
                "evidence_snippet": evidence_snippet,
            }
        )
    return assessments


def corroboration_ratio(assessments: list[dict]) -> float | None:
    """Score claim support from 0 to 1; None when no themes are claimed.

    mentioned_only earns partial credit: the claim recurs across fields but
    lacks operational evidence, so it is weaker than corroboration yet
    stronger than silence.
    """
    if not assessments:
        return None
    credit = {"corroborated": 1.0, "mentioned_only": 0.4, "unsupported": 0.0}
    total = sum(credit[item["support_level"]] for item in assessments)
    return total / len(assessments)
