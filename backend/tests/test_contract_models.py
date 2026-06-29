from decimal import Decimal

from sqlalchemy import create_engine, inspect

from app.database import Base
from app.models import Contract, ContractReview, ContractRiskFlag, ContractRubricScore


def test_contract_review_tables_are_registered_with_expected_defaults() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    assert {
        "contracts",
        "contract_reviews",
        "contract_rubric_scores",
        "contract_risk_flags",
    }.issubset(inspector.get_table_names())

    status = next(
        column
        for column in inspector.get_columns("contracts")
        if column["name"] == "status"
    )
    assert "draft" in str(status["default"])

    review = ContractReview(
        contract_id=None,  # type: ignore[arg-type]
        model_name="test-model",
        flow_name="contract-review",
        total_score=Decimal("85.00"),
        risk_level="medium",
        executive_summary="Summary",
        recommendation="Recommendation",
        raw_output_json={"result": "ok"},
    )
    score = ContractRubricScore(
        contract_review_id=None,  # type: ignore[arg-type]
        category="Termination",
        score=Decimal("8.00"),
        max_score=Decimal("10.00"),
        explanation="Clear terms.",
    )
    flag = ContractRiskFlag(
        contract_review_id=None,  # type: ignore[arg-type]
        risk_type="auto-renewal",
        severity="high",
        explanation="Renewal notice is short.",
    )

    assert Contract.__table__.c.status.default.arg == "draft"
    assert review.raw_output_json == {"result": "ok"}
    assert score.citation is None
    assert flag.suggested_fix is None
