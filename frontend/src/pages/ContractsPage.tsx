import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  deleteContract,
  getContractReview,
  listContracts,
  listDocuments,
  reviewContract,
  updateContract,
  updateContractReview,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import type {
  Contract,
  ContractReview,
  ContractRiskFlag,
  ContractRubricScore,
  Document,
} from "../types/api";

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

function ReviewPanel({
  review,
  onSave,
}: {
  review: ContractReview;
  onSave: (updated: ContractReview) => void;
}) {
  const { getIdToken } = useAuth();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [editSummary, setEditSummary] = useState("");
  const [editRecommendation, setEditRecommendation] = useState("");
  const [editRiskLevel, setEditRiskLevel] = useState<"low" | "medium" | "high">("medium");
  const [editScore, setEditScore] = useState("");

  function startEditing() {
    setEditSummary(review.executive_summary);
    setEditRecommendation(review.recommendation);
    setEditRiskLevel(review.risk_level as "low" | "medium" | "high");
    setEditScore(String(Number(review.total_score)));
    setEditError(null);
    setEditing(true);
  }

  async function handleSave() {
    setSaving(true);
    setEditError(null);
    try {
      const token = await getIdToken();
      const updated = await updateContractReview(token, review.contract_id, {
        executive_summary: editSummary,
        recommendation: editRecommendation,
        risk_level: editRiskLevel,
        total_score: Number(editScore),
      });
      onSave(updated);
      setEditing(false);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const totalScore = Number(review.total_score);
  const isFake = review.model_name === "placeholder";

  return (
    <div className="review-panel">
      <div className="review-panel__header">
        <div className="review-panel__score">
          {editing ? (
            <input
              className="review-score-input"
              type="number"
              min={0}
              max={100}
              value={editScore}
              onChange={(e) => setEditScore(e.target.value)}
            />
          ) : (
            <>
              <span className="review-panel__score-value">{totalScore}</span>
              <span className="review-panel__score-denom">/100</span>
            </>
          )}
        </div>

        {editing ? (
          <select
            className="review-risk-select"
            value={editRiskLevel}
            onChange={(e) =>
              setEditRiskLevel(e.target.value as "low" | "medium" | "high")
            }
          >
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        ) : (
          <RiskBadge level={review.risk_level} />
        )}

        <span className="review-model-badge">
          {isFake ? "Placeholder reviewer" : review.model_name}
        </span>

        <div className="review-panel__actions">
          {editing ? (
            <>
              <button
                type="button"
                className="table-action"
                onClick={() => void handleSave()}
                disabled={saving}
              >
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                type="button"
                className="table-action table-action--muted"
                onClick={() => setEditing(false)}
                disabled={saving}
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              className="table-action"
              onClick={startEditing}
            >
              Edit review
            </button>
          )}
        </div>
      </div>

      {editError ? (
        <div className="document-error" role="alert" style={{ marginBottom: 16 }}>
          {editError}
        </div>
      ) : null}

      <section className="review-section">
        <h3>Executive summary</h3>
        {editing ? (
          <textarea
            className="review-textarea"
            value={editSummary}
            onChange={(e) => setEditSummary(e.target.value)}
            rows={4}
          />
        ) : (
          <p>{review.executive_summary}</p>
        )}
      </section>

      <section className="review-section">
        <h3>Recommendation</h3>
        {editing ? (
          <textarea
            className="review-textarea"
            value={editRecommendation}
            onChange={(e) => setEditRecommendation(e.target.value)}
            rows={3}
          />
        ) : (
          <p className="review-recommendation">{review.recommendation}</p>
        )}
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
  );
}

function ContractRow({
  contract,
  selected,
  onSelect,
  onDelete,
  onUpdate,
}: {
  contract: Contract;
  selected: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onUpdate: (updated: Contract) => void;
}) {
  const { getIdToken } = useAuth();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editVendor, setEditVendor] = useState("");
  const [editType, setEditType] = useState("");

  function startEditing(e: React.MouseEvent) {
    e.stopPropagation();
    setEditVendor(contract.vendor_name ?? "");
    setEditType(contract.contract_type ?? "");
    setEditing(true);
  }

  async function handleSave(e: React.MouseEvent) {
    e.stopPropagation();
    setSaving(true);
    try {
      const token = await getIdToken();
      const updated = await updateContract(token, contract.id, {
        vendor_name: editVendor.trim() || null,
        contract_type: editType.trim() || null,
      });
      onUpdate(updated);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  function handleCancel(e: React.MouseEvent) {
    e.stopPropagation();
    setEditing(false);
  }

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    onDelete(contract.id);
  }

  const formattedDate = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(contract.created_at));

  return (
    <tr
      className={`contract-row${selected ? " contract-row--selected" : ""}`}
      onClick={() => !editing && onSelect(contract.id)}
      style={{ cursor: editing ? "default" : "pointer" }}
    >
      <td>
        {editing ? (
          <input
            className="row-edit-input"
            type="text"
            value={editVendor}
            onChange={(e) => setEditVendor(e.target.value)}
            placeholder="Vendor name"
            onClick={(e) => e.stopPropagation()}
            autoFocus
          />
        ) : (
          contract.vendor_name ?? <em>Unknown vendor</em>
        )}
      </td>
      <td>
        {editing ? (
          <input
            className="row-edit-input"
            type="text"
            value={editType}
            onChange={(e) => setEditType(e.target.value)}
            placeholder="Contract type"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="capitalize">{contract.contract_type ?? <em>—</em>}</span>
        )}
      </td>
      <td>
        <span className="status-pill">{contract.status}</span>
      </td>
      <td>{formattedDate}</td>
      <td className="row-actions">
        {editing ? (
          <>
            <button
              type="button"
              className="table-action"
              onClick={(e) => void handleSave(e)}
              disabled={saving}
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              className="table-action table-action--muted"
              onClick={handleCancel}
              disabled={saving}
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="table-action"
              onClick={(e) => {
                e.stopPropagation();
                onSelect(contract.id);
              }}
            >
              {selected ? "Hide" : "Review"}
            </button>
            <button
              type="button"
              className="table-action"
              onClick={startEditing}
            >
              Edit
            </button>
            <button
              type="button"
              className="table-action table-action--danger"
              onClick={handleDelete}
            >
              Delete
            </button>
          </>
        )}
      </td>
    </tr>
  );
}

export function ContractsPage() {
  const { user, loading: authLoading, signInWithGoogle, getIdToken } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [vendorName, setVendorName] = useState("");
  const [contractType, setContractType] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedContractId, setSelectedContractId] = useState<string | null>(null);
  const [loadedReviews, setLoadedReviews] = useState<Record<string, ContractReview>>({});
  const [reviewLoading, setReviewLoading] = useState(false);

  const processedDocuments = documents.filter((d) => d.status === "processed");

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      setListLoading(true);
      try {
        const token = await getIdToken();
        const [docs, contractList] = await Promise.all([
          listDocuments(token, signal),
          listContracts(token, signal),
        ]);
        setDocuments(docs);
        setContracts(contractList);
      } finally {
        setListLoading(false);
      }
    },
    [getIdToken],
  );

  useEffect(() => {
    if (!user) {
      setDocuments([]);
      setContracts([]);
      return;
    }
    const controller = new AbortController();
    setError(null);
    refresh(controller.signal).catch((err: unknown) => {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Could not load data");
    });
    return () => controller.abort();
  }, [user, refresh]);

  async function handleSelectContract(contractId: string) {
    if (selectedContractId === contractId) {
      setSelectedContractId(null);
      return;
    }
    setSelectedContractId(contractId);
    if (loadedReviews[contractId]) return;

    setReviewLoading(true);
    try {
      const token = await getIdToken();
      const review = await getContractReview(token, contractId);
      setLoadedReviews((prev) => ({ ...prev, [contractId]: review }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load review");
    } finally {
      setReviewLoading(false);
    }
  }

  async function handleDelete(contractId: string) {
    if (
      !window.confirm(
        "Permanently delete this contract and its review? This cannot be undone.",
      )
    )
      return;

    try {
      const token = await getIdToken();
      await deleteContract(token, contractId);
      setContracts((prev) => prev.filter((c) => c.id !== contractId));
      if (selectedContractId === contractId) setSelectedContractId(null);
      setLoadedReviews((prev) => {
        const next = { ...prev };
        delete next[contractId];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  function handleContractUpdated(updated: Contract) {
    setContracts((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  function handleReviewUpdated(contractId: string, updated: ContractReview) {
    setLoadedReviews((prev) => ({ ...prev, [contractId]: updated }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDocumentId) {
      setError("Select a processed document to review");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const token = await getIdToken();
      const result = await reviewContract(token, {
        document_id: selectedDocumentId,
        vendor_name: vendorName.trim() || undefined,
        contract_type: contractType.trim() || undefined,
      });
      setLoadedReviews((prev) => ({ ...prev, [result.contract.id]: result.review }));
      setSelectedContractId(result.contract.id);
      setVendorName("");
      setContractType("");
      setSelectedDocumentId("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (authLoading) {
    return <main className="documents-page">Checking your account…</main>;
  }

  if (!user) {
    return (
      <main className="documents-page documents-page--centered">
        <p className="eyebrow">Contract review</p>
        <h1 className="page-title">Sign in to review HOA contracts.</h1>
        <p className="page-copy">
          Contract reviews are private and scoped to your organization.
        </p>
        <button
          className="button button--primary"
          type="button"
          onClick={() => void signInWithGoogle()}
        >
          Continue with Google
        </button>
      </main>
    );
  }

  return (
    <main className="documents-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Contract review</p>
          <h1 className="page-title">Review vendor contracts.</h1>
        </div>
        <p className="page-copy">
          Select a processed document to generate a contract review.
        </p>
      </div>

      <section className="upload-panel" aria-labelledby="review-heading">
        <div>
          <h2 id="review-heading">New contract review</h2>
          <p>
            Upload and process a contract on the{" "}
            <a href="/documents" className="inline-link">
              Documents page
            </a>{" "}
            first, then select it here.
          </p>
        </div>
        <form className="upload-form" onSubmit={handleSubmit}>
          <label>
            Document
            <select
              value={selectedDocumentId}
              onChange={(e) => setSelectedDocumentId(e.target.value)}
              disabled={submitting}
              required
            >
              <option value="">— select a processed document —</option>
              {processedDocuments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.original_filename}
                </option>
              ))}
            </select>
            {processedDocuments.length === 0 && !listLoading ? (
              <span className="field-hint">
                No processed documents found. Upload and process a contract first.
              </span>
            ) : null}
          </label>
          <label>
            Vendor name <span className="field-optional">(optional)</span>
            <input
              type="text"
              value={vendorName}
              onChange={(e) => setVendorName(e.target.value)}
              placeholder="e.g. ABC Landscaping"
              disabled={submitting}
            />
          </label>
          <label>
            Contract type <span className="field-optional">(optional)</span>
            <input
              type="text"
              value={contractType}
              onChange={(e) => setContractType(e.target.value)}
              placeholder="e.g. landscaping, maintenance, security"
              disabled={submitting}
            />
          </label>
          <button
            className="button button--primary"
            type="submit"
            disabled={submitting || !selectedDocumentId}
          >
            {submitting ? "Reviewing…" : "Review contract"}
          </button>
        </form>
      </section>

      {error ? (
        <div className="document-error" role="alert">
          {error}
        </div>
      ) : null}

      <section className="document-list" aria-labelledby="contracts-heading">
        <div className="document-list__heading">
          <h2 id="contracts-heading">Contract reviews</h2>
          <span>{contracts.length} total</span>
        </div>

        {listLoading ? (
          <p className="empty-state">Loading…</p>
        ) : contracts.length === 0 ? (
          <p className="empty-state">
            No contract reviews yet. Submit the form above to generate the first review.
          </p>
        ) : (
          <div className="document-table-wrap">
            <table className="document-table">
              <thead>
                <tr>
                  <th>Vendor</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Reviewed</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {contracts.map((c) => (
                  <>
                    <ContractRow
                      key={c.id}
                      contract={c}
                      selected={selectedContractId === c.id}
                      onSelect={(id) => void handleSelectContract(id)}
                      onDelete={(id) => void handleDelete(id)}
                      onUpdate={handleContractUpdated}
                    />
                    {selectedContractId === c.id ? (
                      <tr key={`${c.id}-review`}>
                        <td colSpan={5} className="review-cell">
                          {reviewLoading && !loadedReviews[c.id] ? (
                            <p className="empty-state">Loading review…</p>
                          ) : loadedReviews[c.id] ? (
                            <ReviewPanel
                              review={loadedReviews[c.id]}
                              onSave={(updated) =>
                                handleReviewUpdated(c.id, updated)
                              }
                            />
                          ) : null}
                        </td>
                      </tr>
                    ) : null}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
