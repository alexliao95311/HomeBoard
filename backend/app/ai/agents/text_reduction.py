from app.ai.providers.base import AIProvider

# Chunk size for the extraction pass: comfortably small for every model in
# settings.ALLOWED_MODELS (all have well over 100K-token context windows), leaving
# plenty of headroom for the extraction prompt and the model's reply.
CHUNK_CHARS = 90_000

_EXTRACTION_SYSTEM_PROMPT = (
    "You extract facts from one part of a larger contract/proposal document so they can be "
    "combined with facts extracted from the other parts into a single full analysis later. "
    "Preserve exact wording — do not paraphrase or summarize loosely."
)


def _extraction_user_prompt(chunk_text: str, chunk_index: int, total_chunks: int) -> str:
    return (
        f"This is part {chunk_index} of {total_chunks} of one document (parts are given in "
        "original reading order; related content may also appear in other parts).\n\n"
        "Extract every clause in this part relevant to any of these topics, verbatim where "
        "possible, together with its section number/heading if present:\n"
        "- Pricing, fees, payment terms, escalation, late fees\n"
        "- Scope of work: included/excluded services, deliverables, performance standards\n"
        "- Term, duration, renewal, auto-renewal, notice required for non-renewal\n"
        "- Cancellation / termination-for-convenience / termination-for-cause / exit penalties\n"
        "- Insurance, liability caps, indemnification, required exhibits\n"
        "- Vendor obligations, subcontractors, licensing, bonding\n"
        "- Compliance / document completeness details\n\n"
        "Output plain text bullet points. For each clause found, include the section number or "
        "heading (if present) and an exact quoted excerpt. Do not skip anything relevant just "
        "because it looks minor. If this part has no relevant content, output exactly "
        "'No relevant clauses in this part.' Do not add commentary, opinions, or scoring — "
        "extraction only.\n\n"
        f"PART {chunk_index} OF {total_chunks} TEXT:\n{chunk_text}"
    )


def _split_into_chunks(text: str, target_size: int) -> list[str]:
    remaining = text.strip()
    chunks: list[str] = []
    max_size = int(target_size * 1.25)
    min_break = int(target_size * 0.75)

    while remaining:
        if len(remaining) <= max_size:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n\n", min_break, max_size + 1)
        if split_at < min_break:
            split_at = remaining.rfind("\n", min_break, max_size + 1)
        if split_at < min_break:
            split_at = remaining.rfind(" ", min_break, max_size + 1)
        if split_at < min_break:
            split_at = target_size

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    return chunks


def reduce_text_to_budget(
    text: str,
    budget_chars: int,
    provider: AIProvider,
    model: str,
    label: str = "document",
) -> str:
    """Return text as-is if it fits the budget; otherwise run a map-reduce extraction pass
    over the whole document (in chunks) so every part is read by the model at least once,
    then return the combined extracted facts in place of the raw text."""
    if len(text) <= budget_chars:
        return text

    chunks = _split_into_chunks(text, CHUNK_CHARS)
    extracts = []
    for index, chunk in enumerate(chunks, start=1):
        raw = provider.complete(
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": _extraction_user_prompt(chunk, index, len(chunks))},
            ],
            model=model,
        )
        extracts.append(
            f"--- Extracted facts from part {index}/{len(chunks)} of the {label} ---\n{raw.strip()}"
        )

    combined = "\n\n".join(extracts)
    if len(combined) > budget_chars:
        # Extremely unlikely (would require an enormous number of dense clauses), but
        # guard against ever exceeding the budget passed to the final synthesis call.
        combined = combined[:budget_chars] + "\n[... truncated for length ...]"
    return combined
