import json

from pydantic import BaseModel, Field, ValidationError

from app.ai.providers.base import AIProvider
from app.ai.providers.openrouter_provider import AIProviderError
from app.ai.agents.text_reduction import CHUNK_CHARS, reduce_text_to_budget

# Total character budget shared across all documents being compared in a single call.
# Every model in settings.ALLOWED_MODELS has a context window well over 100K tokens, so
# this leaves ample room for the prompt scaffolding, per-document rubric summaries, and
# the model's reply even when each document's share is used in full.
_TOTAL_CHAR_BUDGET = 350_000

_SYSTEM_PROMPT = (
    "You are an HOA contract comparison specialist helping a homeowners association board "
    "choose between multiple vendor documents. "
    "You are NOT a lawyer and this is NOT legal advice. "
    "Base your comparison strictly on the contract texts and rubric scores provided. "
    "Do not invent facts. "
    "\n\n"
    "DOCUMENT TYPE AWARENESS:\n"
    "The documents being compared may be a mix of types: vendor proposals, draft contracts, "
    "signed contracts, or amendments. If they are different types (e.g. one proposal and one "
    "formal contract), call this out explicitly — comparing a proposal to a signed contract is "
    "inherently uneven, and the board should understand this context before deciding.\n"
    "\n\n"
    "MONETARY AMOUNTS — CRITICAL: "
    "NEVER use the dollar sign ($) anywhere in your response — not in JSON strings, not in "
    "explanations, not in examples. Write numbers only: '3,550' not '$3,550', '1M' not '$1M', "
    "'30K' not '$30K'. This rule has zero exceptions.\n"
    "\n\n"
    "HOA FEE STRUCTURE — CRITICAL:\n"
    "Never compare documents based on headline monthly fees alone. The true cost is the SUM "
    "of all fee components: base retainer, per-project charges, percentage-of-cost surcharges, "
    "percentage-of-claim fees, invoice markups, and add-on service fees. A vendor with a low "
    "monthly retainer but 8% project oversight fees can easily cost the HOA 2-3x more than a "
    "vendor with a higher flat fee. When comparing, always:\n"
    "- Identify and compare every fee component across all documents side by side.\n"
    "- Call out any percentage-of-project or percentage-of-claim billing as HIGH RISK. "
    "The HOA's preferred model is HOURLY billing. Percentage billing creates a direct conflict "
    "of interest: the vendor profits more when projects cost more.\n"
    "- Estimate the total annual cost for each under a realistic scenario (2-3 typical projects "
    "per year) so the board can compare true cost of ownership, not just base fees.\n"
    "- Flag any document that buries variable fees in schedules or exhibits.\n"
    "\n\n"
    "FORMATTING:\n"
    "When writing markdown inside JSON fields, use bullet points and ## headings only. "
    "NEVER use markdown tables, pipe characters (|), or grid formatting. "
    "All comparisons must be written as bullet-pointed lists, one contract per bullet. "
    "Your entire response must be a single valid JSON object. "
    "Do not include any text before or after the JSON. "
    "Do not use markdown code blocks."
)

_USER_PROMPT_TEMPLATE = """\
Compare the following {n} HOA vendor documents for a homeowners association board.
Each document includes its full text and AI-generated rubric scores from a prior review.

{contract_blocks}

BEFORE WRITING: Note the document type of each (Vendor Proposal / Draft Contract / Signed
Contract / Amendment). If the types differ, call this out in the ## Document Types section.

Return a JSON object with exactly these fields:
{{
  "summary": "<Board-ready markdown comparison. Use ## headings and bullet points ONLY. No markdown tables, no pipe characters, no grid formatting — every comparison must be a bullet list. Include exactly these sections in order:

## Document Types
For each document, one bullet: vendor name — document type (Proposal / Draft / Signed / Amendment). If types differ, explain why this makes the comparison uneven and what the board should do about it (e.g. request a formal contract draft from the proposal vendor before deciding).

## Recommendation
Which document the board should favor, in one sentence, and the single most important reason. If one is a proposal and one is a signed contract, recommend requesting a matching formal contract draft before making a final decision.

## Fee Structure Comparison
For each document, a sub-bullet block:
- Vendor name: [document type]
  - Base / retainer fee (amount and frequency — no dollar signs, write numerically)
  - Per-project fees (amount or percentage — flag any percentage-of-cost as HIGH RISK conflict of interest)
  - Percentage-of-claim fees (flag if present)
  - Invoice markups or surcharges
  - Add-on fees for services that should be in the base
  - Estimated total annual cost assuming 2-3 typical projects (show the math)
Close with a bullet comparing total estimated cost across all documents.

## Risk and Liability Comparison
For each document, bullet the liability cap, insurance requirements, indemnification direction, and any missing protections. For proposals, note what the formal contract must include.

## Key Differences
Up to 5 bullets on the most important differences across all documents — cancellation terms, scope clarity, vendor obligations, fee transparency.

## Recommended Next Step
One concrete action for the board: which document to select, or what to negotiate/request before deciding.

Do not include an AI disclaimer in this field.>",

  "per_contract": [
    {{
      "contract_id": "<exact UUID string as provided>",
      "strengths": ["<specific strength from the document text, max 3>"],
      "weaknesses": ["<specific weakness, max 3 — always include fee structure concerns if percentage billing is present; for proposals, note key gaps that must appear in the formal contract>"],
      "verdict": "<one-sentence board-facing verdict. For proposals: state what the formal contract must include. For contracts: state whether to select, negotiate, or reject, and include a total cost estimate if percentage fees are present.>"
    }}
  ],
  "critical_differences": [
    "<the single most important difference the board must understand before deciding — lead with document type differences if types differ, then fee structure differences if any document uses percentage billing; max 4 items>"
  ]
}}

Important: include one entry in per_contract for every document provided, in the same order,
using the exact contract_id values given.
"""


class PerContractResult(BaseModel):
    contract_id: str
    strengths: list[str]
    weaknesses: list[str]
    verdict: str


class ContractComparisonResult(BaseModel):
    summary: str
    per_contract: list[PerContractResult] = Field(min_length=1)
    critical_differences: list[str] = Field(default_factory=list)


class ContractComparisonError(Exception):
    """Raised when the AI agent cannot produce a valid comparison."""


def _build_contract_block(
    contract_id: str,
    vendor_name: str | None,
    contract_type: str | None,
    total_score: float,
    risk_level: str,
    rubric_rows: list[dict],
    contract_text: str,
    budget_chars: int,
    provider: AIProvider,
    model: str,
) -> str:
    rubric_summary = ", ".join(
        f"{r['category']}: {r['score']}/{r['max_score']}" for r in rubric_rows
    )
    text = reduce_text_to_budget(
        contract_text,
        budget_chars,
        provider,
        model,
        label=f"document from {vendor_name or 'this vendor'}",
    )

    return (
        f"=== DOCUMENT: {vendor_name or 'Unknown vendor'} ===\n"
        f"ID: {contract_id}\n"
        f"User-provided type hint: {contract_type or 'not specified'}\n"
        f"Score: {total_score:.0f}/100  Risk: {risk_level}\n"
        f"Rubric breakdown: {rubric_summary}\n\n"
        f"Document text (read carefully to determine actual document type):\n{text}\n"
    )


def run_fake_comparison(
    contracts_info: list[dict],
) -> ContractComparisonResult:
    per_contract = [
        PerContractResult(
            contract_id=c["contract_id"],
            strengths=[
                "Competitive pricing relative to scope of services",
                "Clear scope of work with defined deliverables",
            ],
            weaknesses=[
                "Limited liability protections for the HOA",
                "Termination notice period is longer than industry standard",
            ],
            verdict=(
                f"{c['vendor_name'] or 'This vendor'} offers reasonable terms "
                f"but requires negotiation on liability and cancellation clauses before signing."
            ),
        )
        for c in contracts_info
    ]

    names = [c["vendor_name"] or "Unknown" for c in contracts_info]
    best = max(contracts_info, key=lambda c: c["total_score"])
    best_name = best["vendor_name"] or "the top-ranked vendor"

    summary = (
        f"## Board Recommendation\n\n"
        f"After reviewing all {len(contracts_info)} contracts, **{best_name}** is the recommended choice "
        f"based on its superior rubric score and more favorable risk profile. "
        f"However, all contracts reviewed require negotiation on liability caps and insurance requirements "
        f"before the board countersigns.\n\n"
        f"## Price and Value\n\n"
        f"Pricing across the submitted contracts ({', '.join(names)}) varies. "
        f"{best_name} provides the strongest value relative to its scope, "
        f"though all contracts include annual escalation provisions that the board should cap during negotiation.\n\n"
        f"## Risk and Liability\n\n"
        f"None of the contracts specify adequate liability coverage minimums or attach certificates of insurance. "
        f"The board should require minimum $1M general liability coverage from any selected vendor "
        f"before execution.\n\n"
        f"## Key Term Differences\n\n"
        f"Termination notice periods and cure windows vary across contracts. "
        f"The board should standardize on a 30-day termination-for-convenience clause and "
        f"add explicit termination-for-cause language to whichever contract is selected.\n\n"
        f"## Action Required\n\n"
        f"Select {best_name} as the preferred vendor, circulate the contract for attorney review, "
        f"and negotiate the three items listed under critical differences before the next board meeting.\n\n"
        f"*Note: This is a placeholder comparison generated by the fake reviewer.*"
    )

    return ContractComparisonResult(
        summary=summary,
        per_contract=per_contract,
        critical_differences=[
            "Liability caps: all contracts cap vendor liability below acceptable HOA exposure — negotiate upward",
            "Insurance minimums: no contract attaches a certificate of insurance — require before signing",
            "Annual escalation: all contracts allow uncapped price increases — negotiate a CPI-linked ceiling",
            f"Termination notice: review and standardize before countersigning {best_name}'s contract",
        ],
    )


def run_ai_comparison(
    contracts_info: list[dict],
    provider: AIProvider,
    model: str,
) -> ContractComparisonResult:
    per_contract_budget = max(_TOTAL_CHAR_BUDGET // max(len(contracts_info), 1), CHUNK_CHARS)
    contract_blocks = "\n\n".join(
        _build_contract_block(
            contract_id=c["contract_id"],
            vendor_name=c["vendor_name"],
            contract_type=c["contract_type"],
            total_score=c["total_score"],
            risk_level=c["risk_level"],
            rubric_rows=c["rubric_rows"],
            contract_text=c["contract_text"],
            budget_chars=per_contract_budget,
            provider=provider,
            model=model,
        )
        for c in contracts_info
    )

    prompt = _USER_PROMPT_TEMPLATE.format(
        n=len(contracts_info),
        contract_blocks=contract_blocks,
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
        raise ContractComparisonError(str(exc)) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractComparisonError(
            f"Model returned invalid JSON: {exc}. Raw output: {raw[:300]}"
        ) from exc

    try:
        return ContractComparisonResult.model_validate(data)
    except ValidationError as exc:
        raise ContractComparisonError(
            f"Model output failed schema validation: {exc}"
        ) from exc
