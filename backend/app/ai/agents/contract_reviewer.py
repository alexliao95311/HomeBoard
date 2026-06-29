import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.ai.providers.base import AIProvider
from app.ai.providers.openrouter_provider import AIProviderError

_MAX_TEXT_CHARS = 14_000

_SYSTEM_PROMPT = (
    "You are an HOA contract review assistant helping a homeowners association board "
    "evaluate vendor contracts. "
    "You are NOT a lawyer and this output is NOT legal advice — always state this clearly. "
    "Do not invent facts: only draw conclusions from what the contract text explicitly states. "
    "When completing citation fields, quote the exact sentence or closest phrase from the "
    "contract; set citation to null only if the contract is silent on that point. "
    "When writing monetary amounts, never use the $ symbol — write the number only "
    "(e.g. write '3,550' not '$3,550'). "
    "Your entire response must be a single valid JSON object. "
    "Do not include any text before or after the JSON. "
    "Do not use markdown code blocks."
)

_USER_PROMPT_TEMPLATE = """\
Analyze the HOA vendor contract below and return a JSON review.

Contract context:
- Vendor: {vendor_name}
- Contract type: {contract_type}

Score exactly these 8 rubric categories in this order (do not add, remove, or rename any):
1. "Price / Value"                 — max 20 points
2. "Scope Clarity"                 — max 15 points
3. "Term / Cancellation"           — max 15 points
4. "Liability / Insurance"         — max 15 points
5. "Vendor Obligations"            — max 10 points
6. "Payment Terms"                 — max 10 points
7. "Compliance / Doc Completeness" — max 10 points
8. "HOA Flexibility"               — max  5 points

`total_score` must equal the exact integer sum of all 8 rubric scores (range 0–100).

Required JSON schema (fill every field, preserve field names exactly):
{{
  "executive_summary": "<Markdown-formatted breakdown of the contract for an HOA board. Use ## for section headings and blank lines between sections. Include exactly these sections in order: ## Contract Overview (parties, service type, purpose); ## Financial Terms (total cost, payment schedule, escalation, late fees, deposits); ## Scope of Work (bullet list of what is included; bullet list of what is explicitly excluded; note any missing performance standards); ## Term & Renewal (start/end dates, auto-renewal, notice requirements); ## Cancellation (termination-for-convenience terms, termination-for-cause terms, any penalties); ## Insurance & Liability (coverage types, liability caps, indemnification); ## Vendor Obligations (key deliverables, reporting, subcontractors, licensing); ## Notable Strengths (2–3 bullet points); ## Notable Concerns (2–3 bullet points). Only reference what the contract explicitly states; write 'The contract is silent on X' when a topic is not addressed. No AI disclaimers in this field.>",
  "recommendation": "<Markdown-formatted recommendation. Start with a bold verdict: '**VERDICT: ACCEPT**', '**VERDICT: NEGOTIATE BEFORE SIGNING**', or '**VERDICT: REJECT**'. Follow with a one-sentence rationale. Then a numbered list of specific action items — for ACCEPT: confirmations required before countersigning; for NEGOTIATE: exact clause changes with locations; for REJECT: primary reasons and what a replacement contract must include.>",
  "risk_level": "low" | "medium" | "high",
  "total_score": <integer 0–100>,
  "rubric_scores": [
    {{
      "category": "<exact category name from the list above>",
      "score": <integer>,
      "max_score": <integer>,
      "explanation": "<1–2 sentences citing what the contract says or is silent on>",
      "citation": "<Best available reference from the document + exact quoted phrase. Use whatever locator the document provides: section number, clause heading, paragraph title, table heading, or — if the document has none — the first few words of the relevant paragraph as a locator (e.g. 'Under the paragraph beginning \\"The Vendor shall maintain...\\"'). Always include an exact verbatim quote in addition to the locator. Set to null only if the contract is completely silent on this category.>"
    }}
  ],
  "risk_flags": [
    {{
      "risk_type": "<short name for the risk>",
      "severity": "low" | "medium" | "high",
      "explanation": "<explanation based only on contract text>",
      "citation": "<Best available locator + exact verbatim quote, same format as rubric_scores citations. Null only if the risk arises purely from the contract's silence on a topic.>",
      "suggested_fix": "<negotiation suggestion referencing the specific clause or location to revise, or null>"
    }}
  ],
  "board_questions": [
    {{
      "question": "<specific question the board should ask the vendor before signing>",
      "section": "<section number or heading this question relates to, or null if it concerns a gap>"
    }}
  ],
  "negotiation_points": [
    {{
      "point": "<specific change the board should negotiate>",
      "section": "<section number or heading of the clause to revise, or null if adding a new clause>"
    }}
  ]
}}

CONTRACT TEXT:
{contract_text}
"""


class RubricScoreResult(BaseModel):
    category: str
    score: int = Field(ge=0)
    max_score: int = Field(ge=1)
    explanation: str
    citation: str | None = None


class RiskFlagResult(BaseModel):
    risk_type: str
    severity: Literal["low", "medium", "high"]
    explanation: str
    citation: str | None = None
    suggested_fix: str | None = None


class BoardQuestionResult(BaseModel):
    question: str
    section: str | None = None


class NegotiationPointResult(BaseModel):
    point: str
    section: str | None = None


class ContractReviewResult(BaseModel):
    executive_summary: str
    recommendation: str
    risk_level: Literal["low", "medium", "high"]
    total_score: int = Field(ge=0, le=100)
    rubric_scores: list[RubricScoreResult] = Field(min_length=1)
    risk_flags: list[RiskFlagResult]
    board_questions: list[BoardQuestionResult] = Field(default_factory=list)
    negotiation_points: list[NegotiationPointResult] = Field(default_factory=list)


class ContractReviewError(Exception):
    """Raised when the AI agent cannot produce a valid review."""


# Scores: 15+11+10+11+8+8+8+4 = 75
_FAKE_RESULT = ContractReviewResult(
    executive_summary=(
        "## Contract Overview\n\n"
        "This is a 12-month landscaping services agreement between Maplewood HOA (\"the Association\") "
        "and ABC Landscaping LLC (\"the Vendor\"). The contract covers routine grounds maintenance "
        "for all HOA common areas including the front entrance, pool deck perimeter, walking paths, "
        "and retention pond landscaping.\n\n"
        "## Financial Terms\n\n"
        "Monthly fee: **$2,500 ($30,000 annually)**, invoiced on the first of each month and due "
        "within 30 days. A 1.5% monthly late fee applies to overdue balances. The contract includes "
        "an automatic annual price escalation of **up to 5%** with no board approval required — "
        "potentially raising the annual cost to $31,500 or more in subsequent years.\n\n"
        "## Scope of Work\n\n"
        "**Included:**\n"
        "- Weekly lawn mowing and edging\n"
        "- Bi-monthly shrub trimming\n"
        "- Seasonal flower bed planting (spring and fall)\n"
        "- Monthly irrigation system checks\n"
        "- Monthly mulch replenishment\n\n"
        "**Excluded:**\n"
        "- Tree removal\n"
        "- Pest control\n"
        "- Hardscape repair\n"
        "- Snow removal\n"
        "- Irrigation system repairs\n\n"
        "The contract does not define measurable performance standards or response timeframes for "
        "service complaints.\n\n"
        "## Term & Renewal\n\n"
        "January 1–December 31, with automatic annual renewal unless either party provides written "
        "notice of non-renewal at least 60 days before year-end. There is no cap on the number of "
        "renewal cycles.\n\n"
        "## Cancellation\n\n"
        "Either party may terminate for convenience with **90 days written notice**. The Vendor may "
        "terminate immediately if the HOA fails to pay within 45 days. The HOA may terminate for "
        "cause with 30 days notice and an opportunity to cure; however, \"cause\" is not defined "
        "anywhere in the contract.\n\n"
        "## Insurance & Liability\n\n"
        "The Vendor states that it carries general liability insurance, but no certificate is "
        "attached and minimum coverage amounts are not specified. The Vendor's liability per "
        "incident is **capped at one month's fee ($2,500)** — far below typical HOA exposure "
        "for property damage or injury. The indemnification clause runs one-way in favor of "
        "the Vendor.\n\n"
        "## Vendor Obligations\n\n"
        "The Vendor must assign a named account manager and provide a monthly written service "
        "summary. Subcontractors may be used without prior HOA approval. No licensing or bonding "
        "requirements are stated in the contract.\n\n"
        "## Notable Strengths\n\n"
        "- Comprehensive scope of routine services for the price point\n"
        "- Monthly service summaries provide a basic accountability mechanism\n"
        "- Net-30 payment terms are standard and favorable for HOA cash flow\n\n"
        "## Notable Concerns\n\n"
        "- Uncapped 5% annual escalation with no board vote required\n"
        "- 90-day termination notice locks the HOA in for three months after any decision to switch\n"
        "- $2,500 per-incident liability cap is dangerously low for common-area work\n\n"
        "*Note: This is a placeholder review. All figures and findings above are illustrative only.*"
    ),
    recommendation=(
        "**VERDICT: NEGOTIATE BEFORE SIGNING**\n\n"
        "The core service offering and pricing are reasonable, but three clauses create unacceptable "
        "risk and must be renegotiated before the board countersigns.\n\n"
        "1. **Cap the annual price escalation** (Section 3.1) — Request a fixed cap of 3% per year "
        "tied to CPI-U, with any increase above that cap requiring a written board vote.\n\n"
        "2. **Reduce the termination notice period** (Section 7.2) — Reduce termination-for-convenience "
        "notice from 90 days to 30 days. Add a new termination-for-cause clause with a 10-day cure "
        "window and an enumerated definition of cause (repeated missed visits, lapse of insurance, "
        "safety incidents).\n\n"
        "3. **Raise the liability cap** (Section 9.3) — Replace the $2,500 per-incident cap with "
        "a cap equal to the full annual contract value ($30,000 minimum).\n\n"
        "4. **Require insurance certificates** (Section 9.1) — Amend to specify minimum coverage of "
        "$1M general liability and $500K workers' compensation. Attach the certificate of insurance "
        "as Exhibit A before execution — do not sign without it.\n\n"
        "5. **Add a subcontractor approval clause** (Section 4) — Require written HOA consent before "
        "any third party performs work on HOA property."
    ),
    risk_level="medium",
    total_score=75,
    rubric_scores=[
        RubricScoreResult(
            category="Price / Value",
            score=15,
            max_score=20,
            explanation=(
                "Pricing is $2,500/month ($30,000 annually) which is competitive, but the uncapped "
                "5% annual escalation clause allows costs to rise to $31,500+ without board approval."
            ),
            citation='Section 3.1 (Fees): "The monthly service fee shall be $2,500, subject to an annual '
                     'adjustment not to exceed five percent (5%) of the then-current fee."',
        ),
        RubricScoreResult(
            category="Scope Clarity",
            score=11,
            max_score=15,
            explanation=(
                "Exhibit A lists included and excluded services, but defines no performance standards, "
                "service-level targets, or complaint response timeframes."
            ),
            citation='Exhibit A (Scope of Work): "Services include weekly lawn mowing, bi-monthly shrub '
                     'trimming, seasonal plantings, and monthly irrigation checks. Tree removal, pest '
                     'control, and hardscape repair are excluded."',
        ),
        RubricScoreResult(
            category="Term / Cancellation",
            score=10,
            max_score=15,
            explanation=(
                "The 90-day termination-for-convenience notice locks the HOA in for an extended period. "
                "'Cause' for immediate termination is referenced but not defined."
            ),
            citation='Section 7.2 (Termination for Convenience): "Either party may terminate this '
                     'Agreement upon ninety (90) days prior written notice to the other party."',
        ),
        RubricScoreResult(
            category="Liability / Insurance",
            score=11,
            max_score=15,
            explanation=(
                "Vendor is required to carry general liability insurance but certificates are not "
                "attached, coverage minimums are unstated, and the liability cap is one month's fee ($2,500)."
            ),
            citation='Section 9.3 (Limitation of Liability): "Vendor\'s total liability shall not exceed '
                     'the amount of one (1) month\'s service fee paid under this Agreement."',
        ),
        RubricScoreResult(
            category="Vendor Obligations",
            score=8,
            max_score=10,
            explanation=(
                "Section 4 lists core deliverables and requires a named account manager. "
                "No performance benchmarks or remedies for missed service visits are defined."
            ),
            citation='Section 4.1 (Vendor Responsibilities): "Vendor shall assign a dedicated account '
                     'manager and provide a monthly written service summary to the Association."',
        ),
        RubricScoreResult(
            category="Payment Terms",
            score=8,
            max_score=10,
            explanation=(
                "Net-30 invoicing with a 1.5% monthly late fee is standard. "
                "No disputed-invoice or service-credit procedure is defined anywhere in the contract."
            ),
            citation='Section 3.2 (Payment): "Invoices are due within thirty (30) days of receipt. '
                     'Overdue balances accrue interest at 1.5% per month."',
        ),
        RubricScoreResult(
            category="Compliance / Doc Completeness",
            score=8,
            max_score=10,
            explanation=(
                "Section 9.1 references insurance requirements but no certificate is attached as an "
                "exhibit, and minimum coverage amounts are not stated in the contract body."
            ),
            citation='Section 9.1 (Insurance): "Vendor shall maintain general liability insurance in '
                     'amounts sufficient to cover claims arising from Vendor\'s performance hereunder."',
        ),
        RubricScoreResult(
            category="HOA Flexibility",
            score=4,
            max_score=5,
            explanation=(
                "Section 5 permits the HOA to request scope changes, but change-order pricing is at "
                "sole vendor discretion with no cap or approval mechanism."
            ),
            citation='Section 5.2 (Change Orders): "Any changes to the Scope of Work shall be priced '
                     'by Vendor and submitted to the Association for written approval prior to commencement."',
        ),
    ],
    risk_flags=[
        RiskFlagResult(
            risk_type="Excessive Termination Notice",
            severity="medium",
            explanation=(
                "The 90-day termination-for-convenience notice in Section 7.2 locks the HOA into the "
                "contract for three months after a decision to switch vendors, with no shorter exit for cause."
            ),
            citation='Section 7.2 (Termination for Convenience): "Either party may terminate this '
                     'Agreement upon ninety (90) days prior written notice."',
            suggested_fix=(
                "Revise Section 7.2 to reduce convenience notice to 30 days. Add a new Section 7.3 "
                "'Termination for Cause' with a 10-day cure window and an enumerated list of cause events "
                "(missed service visits, failed safety inspections, lapse of insurance)."
            ),
        ),
        RiskFlagResult(
            risk_type="Liability Cap Too Low",
            severity="high",
            explanation=(
                "Section 9.3 caps vendor liability at one month's fee ($2,500 per incident), far below "
                "the HOA's likely exposure for property damage or injury on common areas."
            ),
            citation='Section 9.3 (Limitation of Liability): "Vendor\'s total liability shall not exceed '
                     'the amount of one (1) month\'s service fee paid under this Agreement."',
            suggested_fix=(
                "Negotiate Section 9.3 to raise the cap to the full annual contract value ($30,000). "
                "Amend Section 9.1 to specify minimum coverage of $1M general liability and $500K "
                "workers' compensation, and require the certificate of insurance as Exhibit B."
            ),
        ),
        RiskFlagResult(
            risk_type="Uncapped Annual Escalation",
            severity="medium",
            explanation=(
                "Section 3.1 permits annual fee increases of up to 5% with no board vote required, "
                "no CPI linkage, and no cap on the number of escalation cycles over the life of renewals."
            ),
            citation='Section 3.1 (Fees): "The monthly service fee … subject to an annual adjustment '
                     'not to exceed five percent (5%) of the then-current fee."',
            suggested_fix=(
                "Amend Section 3.1 to tie any escalation to the prior year's CPI-U (capped at 3%), "
                "and require written board approval for any increase above that threshold."
            ),
        ),
    ],
    board_questions=[
        BoardQuestionResult(
            question="Can you provide a certificate of insurance naming the HOA as an additional insured, "
                     "with at least $1M general liability and $500K workers' compensation?",
            section="Section 9.1 (Insurance)",
        ),
        BoardQuestionResult(
            question="What is the process for disputing an invoice or requesting a service credit for "
                     "a missed or substandard service visit?",
            section="Section 3.2 (Payment) — currently silent on dispute resolution",
        ),
        BoardQuestionResult(
            question="Will any subcontractors perform work on HOA property, and will they carry "
                     "the same insurance minimums as your firm?",
            section="Section 4 (Vendor Responsibilities) — subcontractor use is currently unrestricted",
        ),
        BoardQuestionResult(
            question="How is 'cause' defined for purposes of termination, and what documentation "
                     "is required to trigger the for-cause termination clause?",
            section="Section 7 (Termination) — 'cause' is referenced but not defined",
        ),
    ],
    negotiation_points=[
        NegotiationPointResult(
            point="Reduce the termination-for-convenience notice period from 90 days to 30 days.",
            section="Section 7.2 (Termination for Convenience)",
        ),
        NegotiationPointResult(
            point="Add Section 7.3 'Termination for Cause' with a 10-day cure window and an "
                  "enumerated definition of cause events.",
            section="Section 7 (Termination) — new clause needed",
        ),
        NegotiationPointResult(
            point="Raise the per-incident liability cap from $2,500 (one month's fee) to $30,000 "
                  "(full annual contract value).",
            section="Section 9.3 (Limitation of Liability)",
        ),
        NegotiationPointResult(
            point="Specify minimum insurance coverage amounts ($1M GL, $500K WC) directly in the "
                  "contract body and attach a certificate of insurance as Exhibit B.",
            section="Section 9.1 (Insurance)",
        ),
        NegotiationPointResult(
            point="Cap annual fee escalation at 3% tied to CPI-U; require written board approval "
                  "for any increase above that cap.",
            section="Section 3.1 (Fees)",
        ),
        NegotiationPointResult(
            point="Add a subcontractor approval clause requiring written HOA consent before any "
                  "third party performs work on HOA property.",
            section="Section 4 (Vendor Responsibilities) — new clause needed",
        ),
    ],
)


def run_fake_review() -> ContractReviewResult:
    return _FAKE_RESULT


def run_ai_review(
    text_chunks: list[str],
    vendor_name: str | None,
    contract_type: str | None,
    provider: AIProvider,
    model: str,
) -> ContractReviewResult:
    contract_text = "\n\n".join(text_chunks)
    if len(contract_text) > _MAX_TEXT_CHARS:
        contract_text = contract_text[:_MAX_TEXT_CHARS] + "\n[... truncated for length ...]"

    prompt = _USER_PROMPT_TEMPLATE.format(
        vendor_name=vendor_name or "unknown",
        contract_type=contract_type or "general service",
        contract_text=contract_text,
    )

    try:
        raw = provider.complete(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model=model,
        )
    except AIProviderError as exc:
        raise ContractReviewError(str(exc)) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractReviewError(
            f"Model returned invalid JSON: {exc}. Raw output: {raw[:300]}"
        ) from exc

    try:
        return ContractReviewResult.model_validate(data)
    except ValidationError as exc:
        raise ContractReviewError(
            f"Model output failed schema validation: {exc}"
        ) from exc
