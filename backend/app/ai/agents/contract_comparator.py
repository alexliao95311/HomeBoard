import json

from pydantic import BaseModel, Field, ValidationError

from app.ai.providers.base import AIProvider
from app.ai.providers.openrouter_provider import AIProviderError

_MAX_CHARS_PER_CONTRACT = 7_000

_SYSTEM_PROMPT = (
    "You are an HOA contract comparison specialist helping a homeowners association board "
    "choose between multiple vendor contracts. "
    "You are NOT a lawyer and this is NOT legal advice. "
    "Base your comparison strictly on the contract texts and rubric scores provided. "
    "Do not invent facts. "
    "When writing monetary amounts, never use the $ symbol — write the number only "
    "(e.g. write '3,550' not '$3,550'). "
    "Your entire response must be a single valid JSON object. "
    "Do not include any text before or after the JSON. "
    "Do not use markdown code blocks."
)

_USER_PROMPT_TEMPLATE = """\
Compare the following {n} HOA vendor contracts for a homeowners association board.
Each contract includes its full text and its AI-generated rubric scores.

{contract_blocks}

Return a JSON object with exactly these fields:
{{
  "summary": "<Board-ready markdown comparison. Use ## headings. Start with a clear recommendation: which contract the board should favor and why. Then cover: (1) Price and value comparison across all contracts; (2) Risk and liability comparison; (3) Key term differences (cancellation, insurance, scope, obligations). End with a concrete action the board should take. 4–6 paragraphs total. Do not include an AI disclaimer in this field.>",
  "per_contract": [
    {{
      "contract_id": "<exact UUID string as provided>",
      "strengths": ["<specific strength drawn from the contract text, max 3>"],
      "weaknesses": ["<specific weakness drawn from the contract text, max 3>"],
      "verdict": "<one-sentence board-facing verdict for this specific contract>"
    }}
  ],
  "critical_differences": [
    "<the most important difference between the contracts that the board must understand before deciding, drawn from the contract texts — max 4 items>"
  ]
}}

Important: include one entry in per_contract for every contract provided, in the same order, using the exact contract_id values given.
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
) -> str:
    rubric_summary = ", ".join(
        f"{r['category']}: {r['score']}/{r['max_score']}" for r in rubric_rows
    )
    text = contract_text
    if len(text) > _MAX_CHARS_PER_CONTRACT:
        text = text[:_MAX_CHARS_PER_CONTRACT] + "\n[... truncated for length ...]"

    return (
        f"=== CONTRACT: {vendor_name or 'Unknown vendor'} ===\n"
        f"ID: {contract_id}\n"
        f"Type: {contract_type or 'general service'}\n"
        f"Score: {total_score:.0f}/100  Risk: {risk_level}\n"
        f"Rubric: {rubric_summary}\n\n"
        f"Contract text:\n{text}\n"
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
    contract_blocks = "\n\n".join(
        _build_contract_block(
            contract_id=c["contract_id"],
            vendor_name=c["vendor_name"],
            contract_type=c["contract_type"],
            total_score=c["total_score"],
            risk_level=c["risk_level"],
            rubric_rows=c["rubric_rows"],
            contract_text=c["contract_text"],
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
