import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.budget import Budget, BudgetLine
from app.models.transaction import Transaction


def generate_report_json(
    session: Session,
    organization_id: uuid.UUID,
    period_start: date,
    period_end: date,
    budget_id: uuid.UUID | None,
) -> dict:
    """Build a board-facing financial report from transactions using code/math only.

    `budget_vs_actual` compares each budget line's monthly amount (or annual
    amount prorated to a month) against actual expenses in the same category
    for the period — this is meant for roughly month-long periods, matching
    how HOA boards read a monthly treasurer's report.
    """
    transactions = list(session.scalars(
        select(Transaction).where(
            Transaction.organization_id == organization_id,
            Transaction.date >= period_start,
            Transaction.date <= period_end,
        )
    ))

    amounts = [(t, float(t.amount)) for t in transactions]
    # internal transfers between the HOA's own accounts (operating <-> reserve) move
    # cash but aren't real income or expense, so they're excluded from these totals.
    performance_amounts = [(t, amount) for t, amount in amounts if t.transaction_type != "transfer"]

    total_income = sum((amount for _, amount in performance_amounts if amount > 0), 0.0)
    total_expenses = sum((-amount for _, amount in performance_amounts if amount < 0), 0.0)

    expense_totals: dict[str, float] = {}
    income_totals: dict[str, float] = {}
    for t, amount in performance_amounts:
        category = t.category or "Uncategorized"
        if amount < 0:
            expense_totals[category] = expense_totals.get(category, 0.0) - amount
        elif amount > 0:
            income_totals[category] = income_totals.get(category, 0.0) + amount

    expenses_by_category = [
        {"category": category, "amount": round(amount, 2)}
        for category, amount in sorted(expense_totals.items(), key=lambda kv: -kv[1])
    ]
    income_by_category = [
        {"category": category, "amount": round(amount, 2)}
        for category, amount in sorted(income_totals.items(), key=lambda kv: -kv[1])
    ]

    budget_vs_actual: list[dict] = []
    notes: list[str] = []
    if budget_id is not None:
        budget = session.scalar(
            select(Budget).where(
                Budget.id == budget_id,
                Budget.organization_id == organization_id,
            )
        )
        if budget is None:
            notes.append("The requested budget could not be found and was skipped.")
        else:
            budget_lines = list(session.scalars(
                select(BudgetLine).where(BudgetLine.budget_id == budget.id)
            ))
            for line in budget_lines:
                if line.monthly_budget is not None:
                    budget_amount = float(line.monthly_budget)
                elif line.annual_budget is not None:
                    budget_amount = float(line.annual_budget) / 12
                else:
                    budget_amount = None

                actual_amount = expense_totals.get(line.category, 0.0)
                variance = (budget_amount - actual_amount) if budget_amount is not None else None

                budget_vs_actual.append({
                    "category": line.category,
                    "budget_amount": round(budget_amount, 2) if budget_amount is not None else None,
                    "actual_amount": round(actual_amount, 2),
                    "variance": round(variance, 2) if variance is not None else None,
                })

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "executive_summary": {
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_income": round(total_income - total_expenses, 2),
        },
        "expenses_by_category": expenses_by_category,
        "income_by_category": income_by_category,
        "budget_vs_actual": budget_vs_actual,
        "ending_cash_estimate": round(sum((amount for _, amount in amounts), 0.0), 2),
        "notes": notes,
    }
