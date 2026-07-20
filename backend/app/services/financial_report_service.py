import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.budget import Budget, BudgetLine
from app.models.organization import Organization
from app.models.transaction import Transaction


def _fiscal_year_bounds(period_end: date) -> tuple[int, date]:
    """HOA fiscal year runs Oct 1 -> Sep 30, labeled by the calendar year it ends in
    (e.g. Oct 2025 - Sep 2026 is "fiscal year 2026")."""
    fiscal_year = period_end.year + 1 if period_end.month >= 10 else period_end.year
    return fiscal_year, date(fiscal_year - 1, 10, 1)


def _load_transactions(
    session: Session, organization_id: uuid.UUID, start: date, end: date,
) -> list[Transaction]:
    return list(session.scalars(
        select(Transaction).where(
            Transaction.organization_id == organization_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ))


def _performance_amounts(transactions: list[Transaction]) -> list[tuple[Transaction, float]]:
    # internal transfers and same-account reversals move cash but aren't real
    # income or expense, so they're excluded from performance totals.
    return [(t, float(t.amount)) for t in transactions if t.transaction_type != "transfer"]


def _summarize(
    performance_amounts: list[tuple[Transaction, float]],
) -> tuple[float, float, dict[str, float], dict[str, float]]:
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

    return total_income, total_expenses, expense_totals, income_totals


def _category_list(totals: dict[str, float]) -> list[dict]:
    return [
        {"category": category, "amount": round(amount, 2)}
        for category, amount in sorted(totals.items(), key=lambda kv: -kv[1])
    ]


def _fund_section(performance_amounts: list[tuple[Transaction, float]], fund_type: str) -> dict:
    fund_amounts = [(t, amount) for t, amount in performance_amounts if t.fund_type == fund_type]
    income, expenses, expense_totals, income_totals = _summarize(fund_amounts)
    return {
        "executive_summary": {
            "total_income": round(income, 2),
            "total_expenses": round(expenses, 2),
            "net_income": round(income - expenses, 2),
        },
        "expenses_by_category": _category_list(expense_totals),
        "income_by_category": _category_list(income_totals),
    }


def generate_report_json(
    session: Session,
    organization_id: uuid.UUID,
    period_start: date,
    period_end: date,
    budget_id: uuid.UUID | None,
) -> dict:
    """Build a board-facing financial report from transactions using code/math only.

    Mirrors the structure of a standard monthly HOA reporting package: a
    combined summary, separate Operating/Reserve sections (since those are
    reported as distinct funds), and Month + Year-to-Date + Annual-Budget
    columns in `budget_vs_actual` (fiscal year runs Oct 1 -> Sep 30).
    """
    organization = session.get(Organization, organization_id)

    month_transactions = _load_transactions(session, organization_id, period_start, period_end)
    month_amounts = [(t, float(t.amount)) for t in month_transactions]
    month_perf = _performance_amounts(month_transactions)
    month_income, month_expenses, month_expense_totals, month_income_totals = _summarize(month_perf)

    fiscal_year, fiscal_year_start = _fiscal_year_bounds(period_end)
    ytd_start = fiscal_year_start
    ytd_transactions = _load_transactions(session, organization_id, ytd_start, period_end)
    ytd_perf = _performance_amounts(ytd_transactions)
    ytd_income, ytd_expenses, ytd_expense_totals, _ = _summarize(ytd_perf)
    months_elapsed = (
        (period_end.year - fiscal_year_start.year) * 12
        + (period_end.month - fiscal_year_start.month)
        + 1
    )

    operating = _fund_section(month_perf, "operating")
    reserve = _fund_section(month_perf, "reserve")

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
                monthly_budget = float(line.monthly_budget) if line.monthly_budget is not None else None
                annual_budget = float(line.annual_budget) if line.annual_budget is not None else None
                if monthly_budget is None and annual_budget is not None:
                    monthly_budget = annual_budget / 12
                if annual_budget is None and monthly_budget is not None:
                    annual_budget = monthly_budget * 12

                month_actual = month_expense_totals.get(line.category, 0.0)
                month_variance = (monthly_budget - month_actual) if monthly_budget is not None else None

                ytd_budget = monthly_budget * months_elapsed if monthly_budget is not None else None
                ytd_actual = ytd_expense_totals.get(line.category, 0.0)
                ytd_variance = (ytd_budget - ytd_actual) if ytd_budget is not None else None

                budget_vs_actual.append({
                    "category": line.category,
                    "budget_amount": round(monthly_budget, 2) if monthly_budget is not None else None,
                    "actual_amount": round(month_actual, 2),
                    "variance": round(month_variance, 2) if month_variance is not None else None,
                    "ytd_budget_amount": round(ytd_budget, 2) if ytd_budget is not None else None,
                    "ytd_actual_amount": round(ytd_actual, 2),
                    "ytd_variance": round(ytd_variance, 2) if ytd_variance is not None else None,
                    "annual_budget_amount": round(annual_budget, 2) if annual_budget is not None else None,
                })

    transfer_count = sum(1 for t in month_transactions if t.transaction_type == "transfer")
    if transfer_count:
        notes.append(
            f"{transfer_count} transaction(s) in this period are internal transfers or "
            f"same-account corrections and were excluded from income and expenses."
        )

    return {
        "organization_name": organization.name if organization else None,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "fiscal_year": fiscal_year,
        "ytd_start": ytd_start.isoformat(),
        "executive_summary": {
            "total_income": round(month_income, 2),
            "total_expenses": round(month_expenses, 2),
            "net_income": round(month_income - month_expenses, 2),
        },
        "ytd_summary": {
            "total_income": round(ytd_income, 2),
            "total_expenses": round(ytd_expenses, 2),
            "net_income": round(ytd_income - ytd_expenses, 2),
        },
        "operating": operating,
        "reserve": reserve,
        "expenses_by_category": _category_list(month_expense_totals),
        "income_by_category": _category_list(month_income_totals),
        "budget_vs_actual": budget_vs_actual,
        "ending_cash_estimate": round(sum((amount for _, amount in month_amounts), 0.0), 2),
        "notes": notes,
    }
