import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { getContract, getContractReview } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { Contract, ContractReview, ContractRiskFlag, ContractRubricScore } from "../types/api";

function RiskBadge({ level }: { level: string }) {
  const cls =
    level === "high"
      ? "risk-badge risk-badge--high"
      : level === "low"
        ? "risk-badge risk-badge--low"
        : "risk-badge risk-badge--medium";
  return <span className={cls}>{level}</span>;
}

function ScoreBar({ score, max }: { score: number; max: number }) {
  const pct = Math.round((score / max) * 100);
  return (
    <div className="score-bar">
      <div className="score-bar__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function RubricTable({ scores }: { scores: ContractRubricScore[] }) {
  return (
    <table className="rubric-table">
      <thead>
        <tr>
          <th>Category</th>
          <th>Score</th>
          <th>Max</th>
          <th className="rubric-table__bar-col" aria-label="Score bar" />
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        {scores.map((s) => (
          <tr key={s.id}>
            <td>{s.category}</td>
            <td className="rubric-table__num">{Number(s.score)}</td>
            <td className="rubric-table__num">{Number(s.max_score)}</td>
            <td>
              <ScoreBar score={Number(s.score)} max={Number(s.max_score)} />
            </td>
            <td className="rubric-table__explanation">{s.explanation}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RiskFlags({ flags }: { flags: ContractRiskFlag[] }) {
  if (flags.length === 0) return null;
  return (
    <div className="risk-flags">
      {flags.map((f) => (
        <div key={f.id} className={`risk-flag risk-flag--${f.severity}`}>
          <div className="risk-flag__header">
            <span className="risk-flag__type">{f.risk_type}</span>
            <RiskBadge level={f.severity} />
          </div>
          <p className="risk-flag__explanation">{f.explanation}</p>
          {f.suggested_fix ? (
            <p className="risk-flag__fix">
              <strong>Suggested fix:</strong> {f.suggested_fix}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function ContractReviewPage() {
  const { contractId } = useParams<{ contractId: string }>();
  const [searchParams] = useSearchParams();
  const { user, loading: authLoading, getIdToken } = useAuth();

  const [contract, setContract] = useState<Contract | null>(null);
  const [review, setReview] = useState<ContractReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const printOnLoad = searchParams.get("print") === "1";

  useEffect(() => {
    if (!user || !contractId) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const token = await getIdToken();
        const [contractData, reviewData] = await Promise.all([
          getContract(token, contractId, controller.signal),
          getContractReview(token, contractId, controller.signal),
        ]);
        setContract(contractData);
        setReview(reviewData);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Could not load review");
      } finally {
        setLoading(false);
      }
    })();

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, contractId]);

  useEffect(() => {
    if (printOnLoad && !loading && contract && review) {
      const timer = setTimeout(() => window.print(), 200);
      return () => clearTimeout(timer);
    }
  }, [printOnLoad, loading, contract, review]);

  if (authLoading || loading) {
    return (
      <main className="review-page">
        <p className="empty-state">Loading review…</p>
      </main>
    );
  }

  if (error || !contract || !review) {
    return (
      <main className="review-page">
        <Link className="back-link" to="/contracts">
          ← Back to contracts
        </Link>
        <div className="document-error" role="alert">
          {error ?? "Review not found."}
        </div>
      </main>
    );
  }

  const totalScore = Number(review.total_score);
  const isFake = review.model_name === "placeholder";
  const reviewUrl = `/contracts/${contract.id}/review`;

  return (
    <main className="review-page">
      <div className="review-page__topbar no-print">
        <Link className="back-link" to="/contracts">
          ← Back to contracts
        </Link>
        <div className="review-page__topbar-actions">
          <a
            className="button button--secondary review-page__btn"
            href={`${reviewUrl}?print=1`}
            target="_blank"
            rel="noreferrer"
          >
            Export as PDF
          </a>
        </div>
      </div>

      <div className="review-page__header">
        <div>
          <p className="eyebrow">Contract review</p>
          <h1 className="detail-title">
            {contract.vendor_name ?? "Unknown vendor"}
          </h1>
          <div className="document-meta">
            {contract.contract_type ? (
              <span className="capitalize">{contract.contract_type}</span>
            ) : null}
            <span>
              {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
                new Date(contract.created_at),
              )}
            </span>
          </div>
        </div>

        <div className="review-page__score-block">
          <div className="review-panel__score">
            <span className="review-panel__score-value">{totalScore}</span>
            <span className="review-panel__score-denom">/100</span>
          </div>
          <RiskBadge level={review.risk_level} />
          <span className="review-model-badge">
            {isFake ? "Placeholder reviewer" : review.model_name}
          </span>
        </div>
      </div>

      <div className="review-page__body">
        <section className="review-section">
          <h3>Executive summary</h3>
          <p>{review.executive_summary}</p>
        </section>

        <section className="review-section">
          <h3>Recommendation</h3>
          <p className="review-recommendation">{review.recommendation}</p>
        </section>

        <section className="review-section">
          <h3>Rubric scores</h3>
          <RubricTable scores={review.rubric_scores} />
        </section>

        {review.risk_flags.length > 0 ? (
          <section className="review-section">
            <h3>Risk flags</h3>
            <RiskFlags flags={review.risk_flags} />
          </section>
        ) : null}

        <p className="review-disclaimer">
          {isFake
            ? "This review was generated by a placeholder reviewer and must not be used for board decisions."
            : `This review was generated by ${review.model_name} and must be verified by a qualified human before board action.`}
        </p>
      </div>
    </main>
  );
}
