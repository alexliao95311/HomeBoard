import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  aiCategorizeTransactions,
  bulkDeleteTransactions,
  deleteTransaction,
  listDocuments,
  listTransactions,
  updateTransaction,
  uploadCsvTransactions,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import type {
  Document,
  Transaction,
  TransactionUpdateRequest,
  TransactionUploadCsvResponse,
} from "../types/api";
import { TRANSACTION_CATEGORIES } from "../types/api";

const FUND_TYPES = ["operating", "reserve"] as const;

// ── formatting ────────────────────────────────────────────────────────────────

function fmt(amount: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Math.abs(parseFloat(amount)));
}

function fmtSigned(amount: string, type: string) {
  const abs = fmt(amount);
  return type === "expense" ? `−${abs}` : `+${abs}`;
}

// ── summary helpers ───────────────────────────────────────────────────────────

function sumByType(txs: Transaction[], type: "income" | "expense") {
  return txs
    .filter((t) => t.transaction_type === type)
    .reduce((acc, t) => acc + Math.abs(parseFloat(t.amount)), 0);
}

// ── small components ──────────────────────────────────────────────────────────

function TypeBadge({ type }: { type: string }) {
  const cls =
    type === "income"
      ? "status-pill"
      : type === "expense"
        ? "status-pill status-pill--failed"
        : "status-pill status-pill--processing";
  return <span className={cls}>{type}</span>;
}

function ConfidenceDot({ score }: { score: string | null }) {
  if (!score) return null;
  const n = parseFloat(score);
  const color = n >= 0.9 ? "#1f684f" : n >= 0.8 ? "#86631e" : "#7a837f";
  const label = n >= 0.9 ? "High" : n >= 0.8 ? "Medium" : n === 0 ? "None" : "Low";
  return (
    <span title={`Confidence: ${label}`} style={{ color, fontSize: 10, fontWeight: 700 }}>
      {label}
    </span>
  );
}

// ── import panel ──────────────────────────────────────────────────────────────

function ImportPanel({
  csvDocuments,
  onImported,
}: {
  csvDocuments: Document[];
  onImported: () => void;
}) {
  const { getIdToken } = useAuth();
  const [open, setOpen] = useState(true);
  const [documentId, setDocumentId] = useState("");
  const [accountName, setAccountName] = useState("");
  const [fundType, setFundType] = useState("");
  const [docType, setDocType] = useState("bank_statement");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TransactionUploadCsvResponse | null>(null);

  async function runImport(skipDuplicates: boolean) {
    if (!documentId) return;
    setImporting(true);
    setError(null);
    setResult(null);
    try {
      const idToken = await getIdToken();
      const res = await uploadCsvTransactions(idToken, {
        document_id: documentId,
        bank_account_name: accountName.trim() || undefined,
        fund_type: fundType || undefined,
        skip_duplicates: skipDuplicates,
        force_expense: docType !== "bank_statement",
      });
      setResult(res);
      onImported();
      if (res.duplicate_count === 0 || !skipDuplicates) setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await runImport(true);
  }

  return (
    <div className="fin-import-panel">
      <button
        className="fin-import-toggle"
        type="button"
        onClick={() => setOpen((o) => !o)}
      >
        <span>Import CSV transactions</span>
        <span className="fin-import-toggle__arrow">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="fin-import-body">
          {csvDocuments.length === 0 ? (
            <p className="fin-import-hint">
              No CSV documents found. Upload a bank statement or transaction export in the{" "}
              <a href="/documents">Documents</a> workspace first.
            </p>
          ) : (
            <form className="fin-import-form" onSubmit={(e) => void handleSubmit(e)}>
              <label>
                CSV document
                <select
                  value={documentId}
                  onChange={(e) => setDocumentId(e.target.value)}
                  required
                >
                  <option value="">Select a document…</option>
                  {csvDocuments.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.original_filename}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Account name <span className="field-optional">(optional)</span>
                <input
                  type="text"
                  placeholder="e.g. Operating Checking"
                  value={accountName}
                  onChange={(e) => setAccountName(e.target.value)}
                />
              </label>

              <label>
                Fund type <span className="field-optional">(optional)</span>
                <select value={fundType} onChange={(e) => setFundType(e.target.value)}>
                  <option value="">Unspecified</option>
                  <option value="operating">Operating</option>
                  <option value="reserve">Reserve</option>
                </select>
              </label>

              <label>
                Document type
                <select value={docType} onChange={(e) => setDocType(e.target.value)}>
                  <option value="bank_statement">Bank Statement</option>
                  <option value="invoice">Invoice / Bill</option>
                  <option value="check_register">Check Register</option>
                  <option value="expense_report">Expense Report</option>
                </select>
              </label>

              <button
                className="button button--primary"
                type="submit"
                disabled={importing || !documentId}
                style={{ alignSelf: "end" }}
              >
                {importing ? "Importing…" : "Import"}
              </button>
            </form>
          )}

          {error && <p className="document-error" style={{ marginTop: 12 }}>{error}</p>}
        </div>
      )}

      {result && (
        <div className="fin-import-result">
          <div>
            Imported <strong>{result.imported_count}</strong> transaction
            {result.imported_count !== 1 ? "s" : ""}
            {result.skipped_count > 0 && `, skipped ${result.skipped_count} unparseable rows`}.
          </div>

          {result.duplicate_count > 0 && (
            <div className="fin-import-duplicates">
              <span>
                <strong>{result.duplicate_count}</strong> duplicate
                {result.duplicate_count !== 1 ? "s" : ""} skipped — same date, amount &amp; description already exist.
              </span>
              <button
                className="table-action"
                type="button"
                disabled={importing}
                onClick={() => void runImport(false)}
              >
                {importing ? "Importing…" : "Import duplicates anyway"}
              </button>
            </div>
          )}

          {result.warnings.filter((w) => !w.startsWith("[AI")).length > 0 && (
            <details style={{ marginTop: 6 }}>
              <summary style={{ cursor: "pointer", fontSize: 11 }}>
                {result.warnings.length} warning{result.warnings.length !== 1 ? "s" : ""}
              </summary>
              <ul style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 11 }}>
                {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

// ── summary bar ───────────────────────────────────────────────────────────────

function SummaryBar({ transactions }: { transactions: Transaction[] }) {
  const income = sumByType(transactions, "income");
  const expenses = sumByType(transactions, "expense");
  const net = income - expenses;
  const fmtUsd = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

  return (
    <div className="fin-summary">
      <div className="fin-stat fin-stat--income">
        <span className="fin-stat__label">Income</span>
        <span className="fin-stat__value">{fmtUsd(income)}</span>
      </div>
      <div className="fin-stat fin-stat--expense">
        <span className="fin-stat__label">Expenses</span>
        <span className="fin-stat__value">{fmtUsd(expenses)}</span>
      </div>
      <div className={`fin-stat ${net >= 0 ? "fin-stat--net-pos" : "fin-stat--net-neg"}`}>
        <span className="fin-stat__label">Net</span>
        <span className="fin-stat__value">{net >= 0 ? "+" : "−"}{fmtUsd(Math.abs(net))}</span>
      </div>
      <div className="fin-stat fin-stat--count">
        <span className="fin-stat__label">Transactions</span>
        <span className="fin-stat__value">{transactions.length}</span>
      </div>
    </div>
  );
}

// ── filter bar ────────────────────────────────────────────────────────────────

interface Filters {
  dateFrom: string;
  dateTo: string;
  category: string;
  fundType: string;
  txType: string;
}

function FilterBar({
  filters,
  onChange,
  onClear,
  onAiCategorize,
  aiCategorizing,
  aiResult,
}: {
  filters: Filters;
  onChange: (f: Partial<Filters>) => void;
  onClear: () => void;
  onAiCategorize: () => void;
  aiCategorizing: boolean;
  aiResult: { updated_count: number; skipped_count: number } | null;
}) {
  const hasActive =
    filters.dateFrom || filters.dateTo || filters.category || filters.fundType || filters.txType;

  return (
    <div className="fin-filters">
      <label className="fin-filter">
        From
        <input
          type="date"
          value={filters.dateFrom}
          onChange={(e) => onChange({ dateFrom: e.target.value })}
        />
      </label>
      <label className="fin-filter">
        To
        <input
          type="date"
          value={filters.dateTo}
          onChange={(e) => onChange({ dateTo: e.target.value })}
        />
      </label>
      <label className="fin-filter">
        Category
        <select value={filters.category} onChange={(e) => onChange({ category: e.target.value })}>
          <option value="">All categories</option>
          {TRANSACTION_CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </label>
      <label className="fin-filter">
        Fund
        <select value={filters.fundType} onChange={(e) => onChange({ fundType: e.target.value })}>
          <option value="">All funds</option>
          {FUND_TYPES.map((f) => (
            <option key={f} value={f}>{f.charAt(0).toUpperCase() + f.slice(1)}</option>
          ))}
        </select>
      </label>
      <label className="fin-filter">
        Type
        <select value={filters.txType} onChange={(e) => onChange({ txType: e.target.value })}>
          <option value="">All types</option>
          <option value="income">Income</option>
          <option value="expense">Expense</option>
          <option value="transfer">Transfer</option>
        </select>
      </label>
      <div className="fin-filter-actions fin-filter-actions--end">
        {hasActive && (
          <button className="fin-filter-clear" type="button" onClick={onClear}>
            <span>Clear filters</span>
            <span aria-hidden="true">×</span>
          </button>
        )}
        <div className="fin-ai-inline">
          <button
            className="fin-filter-clear fin-filter-clear--primary"
            type="button"
            disabled={aiCategorizing}
            onClick={onAiCategorize}
          >
            {aiCategorizing ? "Categorizing…" : "AI categorize"}
          </button>
          {aiResult && (
            <span className="fin-ai-result">
              {aiResult.updated_count > 0 ? `${aiResult.updated_count} updated` : "Nothing to categorize"}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── inline-edit row ───────────────────────────────────────────────────────────

function EditRow({
  tx,
  onSave,
  onCancel,
}: {
  tx: Transaction;
  onSave: (req: TransactionUpdateRequest) => Promise<void>;
  onCancel: () => void;
}) {
  const [category, setCategory] = useState(tx.category ?? "Uncategorized");
  const [vendor, setVendor] = useState(tx.vendor_name ?? "");
  const [fund, setFund] = useState(tx.fund_type ?? "");
  const [txType, setTxType] = useState(tx.transaction_type);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    await onSave({
      category: category || null,
      vendor_name: vendor.trim() || null,
      fund_type: fund || null,
      transaction_type: txType,
    });
    setSaving(false);
  }

  return (
    <tr className="tx-row tx-row--editing">
      <td></td>
      <td style={{ whiteSpace: "nowrap", color: "#7a837f" }}>{tx.date}</td>
      <td>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{tx.description}</div>
        <input
          className="row-edit-input"
          placeholder="Vendor name"
          value={vendor}
          onChange={(e) => setVendor(e.target.value)}
        />
      </td>
      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
        <span style={{ color: tx.transaction_type === "expense" ? "#7c342a" : "#1f684f", fontVariantNumeric: "tabular-nums" }}>
          {fmtSigned(tx.amount, tx.transaction_type)}
        </span>
      </td>
      <td>
        <select
          className="row-edit-input"
          value={txType}
          onChange={(e) => setTxType(e.target.value)}
        >
          <option value="income">income</option>
          <option value="expense">expense</option>
          <option value="transfer">transfer</option>
        </select>
      </td>
      <td>
        <select
          className="row-edit-input"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {TRANSACTION_CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </td>
      <td>
        <select
          className="row-edit-input"
          value={fund}
          onChange={(e) => setFund(e.target.value)}
        >
          <option value="">—</option>
          {FUND_TYPES.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </td>
      <td className="row-actions">
        <button
          className="table-action"
          type="button"
          disabled={saving}
          onClick={() => void handleSave()}
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button className="table-action table-action--muted" type="button" onClick={onCancel}>
          Cancel
        </button>
      </td>
    </tr>
  );
}

// ── transaction table ─────────────────────────────────────────────────────────

function SortTh({
  col,
  active,
  dir,
  onClick,
  style,
  children,
}: {
  col: string;
  active: string;
  dir: "asc" | "desc";
  onClick: (col: string) => void;
  style?: React.CSSProperties;
  children: React.ReactNode;
}) {
  const isActive = col === active;
  return (
    <th style={style}>
      <button
        type="button"
        className="sort-th-btn"
        onClick={() => onClick(col)}
        aria-sort={isActive ? (dir === "asc" ? "ascending" : "descending") : "none"}
      >
        {children}
        <span className={`sort-indicator${isActive ? " sort-indicator--active" : ""}`}>
          {isActive ? (dir === "asc" ? "▲" : "▼") : "⇅"}
        </span>
      </button>
    </th>
  );
}

function TransactionTable({
  transactions,
  onEdit,
  editingId,
  onSave,
  onCancelEdit,
  selectedIds,
  onToggleSelect,
  onToggleAll,
  onSingleDelete,
  sortCol,
  sortDir,
  onSort,
}: {
  transactions: Transaction[];
  onEdit: (id: string) => void;
  editingId: string | null;
  onSave: (id: string, req: TransactionUpdateRequest) => Promise<void>;
  onCancelEdit: () => void;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onToggleAll: () => void;
  onSingleDelete: (id: string) => void;
  sortCol: string;
  sortDir: "asc" | "desc";
  onSort: (col: string) => void;
}) {
  if (transactions.length === 0) {
    return (
      <div className="empty-state">
        No transactions match the current filters.
      </div>
    );
  }

  const allSelected =
    transactions.length > 0 && transactions.every((t) => selectedIds.has(t.id));
  const someSelected = !allSelected && transactions.some((t) => selectedIds.has(t.id));

  return (
    <div className="document-table-wrap">
      <table className="document-table">
        <thead>
          <tr>
            <th style={{ width: 36 }}>
              <input
                type="checkbox"
                checked={allSelected}
                ref={(el) => { if (el) el.indeterminate = someSelected; }}
                onChange={onToggleAll}
                aria-label="Select all"
              />
            </th>
            <SortTh col="date" active={sortCol} dir={sortDir} onClick={onSort}>Date</SortTh>
            <SortTh col="description" active={sortCol} dir={sortDir} onClick={onSort}>Description / Vendor</SortTh>
            <SortTh col="amount" active={sortCol} dir={sortDir} onClick={onSort} style={{ textAlign: "right" }}>Amount</SortTh>
            <SortTh col="type" active={sortCol} dir={sortDir} onClick={onSort}>Type</SortTh>
            <SortTh col="category" active={sortCol} dir={sortDir} onClick={onSort}>Category</SortTh>
            <SortTh col="fund_type" active={sortCol} dir={sortDir} onClick={onSort}>Fund</SortTh>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) =>
            tx.id === editingId ? (
              <EditRow
                key={tx.id}
                tx={tx}
                onSave={(req) => onSave(tx.id, req)}
                onCancel={onCancelEdit}
              />
            ) : (
              <tr
                key={tx.id}
                className={`tx-row${selectedIds.has(tx.id) ? " tx-row--selected" : ""}${tx.category === "Uncategorized" || !tx.category ? " tx-row--uncategorized" : ""}`}
              >
                <td>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(tx.id)}
                    onChange={() => onToggleSelect(tx.id)}
                    aria-label="Select row"
                  />
                </td>
                <td style={{ whiteSpace: "nowrap", color: "#7a837f" }}>{tx.date}</td>
                <td>
                  <span className="document-name" style={{ maxWidth: 300 }}>{tx.description}</span>
                  {tx.vendor_name && (
                    <span className="document-hash">{tx.vendor_name}</span>
                  )}
                </td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>
                  <span style={{ color: tx.transaction_type === "expense" ? "#7c342a" : "#1f684f" }}>
                    {fmtSigned(tx.amount, tx.transaction_type)}
                  </span>
                </td>
                <td><TypeBadge type={tx.transaction_type} /></td>
                <td>
                  <span style={{ fontSize: 13 }}>{tx.category ?? "—"}</span>
                  {tx.confidence_score && parseFloat(tx.confidence_score) < 0.85 && (
                    <div style={{ marginTop: 2 }}>
                      <ConfidenceDot score={tx.confidence_score} />
                    </div>
                  )}
                </td>
                <td style={{ color: tx.fund_type ? "#315f50" : "#9aa3a0", fontSize: 12, fontWeight: 650, textTransform: "capitalize" }}>
                  {tx.fund_type ?? "—"}
                </td>
                <td className="row-actions">
                  <button
                    className="table-action"
                    type="button"
                    onClick={() => onEdit(tx.id)}
                  >
                    Edit
                  </button>
                  <button
                    className="table-action table-action--danger"
                    type="button"
                    onClick={() => onSingleDelete(tx.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            )
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

const EMPTY_FILTERS: Filters = {
  dateFrom: "",
  dateTo: "",
  category: "",
  fundType: "",
  txType: "",
};

export function FinancialPage() {
  const { user, getIdToken } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingTx, setLoadingTx] = useState(true);
  const [txError, setTxError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [sortCol, setSortCol] = useState<string>("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [aiCategorizing, setAiCategorizing] = useState(false);
  const [aiCategorizeResult, setAiCategorizeResult] = useState<{ updated_count: number; skipped_count: number } | null>(null);

  const csvDocuments = documents.filter(
    (d) => d.content_type === "text/csv" || d.content_type === "text/plain",
  );

  const fetchTransactions = useCallback(async () => {
    if (!user) return;
    setLoadingTx(true);
    setTxError(null);
    try {
      const idToken = await getIdToken();
      setTransactions(await listTransactions(idToken));
    } catch (err) {
      setTxError(err instanceof Error ? err.message : "Could not load transactions");
    } finally {
      setLoadingTx(false);
    }
  }, [user, getIdToken]);

  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    void (async () => {
      try {
        const idToken = await getIdToken();
        setDocuments(await listDocuments(idToken, controller.signal));
      } catch {
        // ignore abort
      } finally {
        setLoadingDocs(false);
      }
    })();
    return () => controller.abort();
  }, [user, getIdToken]);

  useEffect(() => {
    void fetchTransactions();
  }, [fetchTransactions]);

  // Client-side filtering
  const filtered = transactions.filter((tx) => {
    if (filters.dateFrom && tx.date < filters.dateFrom) return false;
    if (filters.dateTo && tx.date > filters.dateTo) return false;
    if (filters.category && tx.category !== filters.category) return false;
    if (filters.fundType && tx.fund_type !== filters.fundType) return false;
    if (filters.txType && tx.transaction_type !== filters.txType) return false;
    return true;
  });

  function handleSort(col: string) {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  }

  const sortedFiltered = [...filtered].sort((a, b) => {
    let cmp = 0;
    switch (sortCol) {
      case "date":
        cmp = a.date.localeCompare(b.date);
        break;
      case "description":
        cmp = a.description.toLowerCase().localeCompare(b.description.toLowerCase());
        break;
      case "amount":
        cmp = parseFloat(a.amount) - parseFloat(b.amount);
        break;
      case "type":
        cmp = a.transaction_type.localeCompare(b.transaction_type);
        break;
      case "category":
        cmp = (a.category ?? "").localeCompare(b.category ?? "");
        break;
      case "fund_type":
        cmp = (a.fund_type ?? "").localeCompare(b.fund_type ?? "");
        break;
    }
    return sortDir === "asc" ? cmp : -cmp;
  });

  async function handleAiCategorize() {
    setAiCategorizing(true);
    setAiCategorizeResult(null);
    try {
      const idToken = await getIdToken();
      const result = await aiCategorizeTransactions(idToken);
      setAiCategorizeResult(result);
      if (result.updated_count > 0) await fetchTransactions();
    } catch (err) {
      alert(err instanceof Error ? err.message : "AI categorization failed");
    } finally {
      setAiCategorizing(false);
    }
  }

  function handleToggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleToggleAll() {
    const visibleIds = filtered.map((t) => t.id);
    const allSelected = visibleIds.every((id) => selectedIds.has(id));
    if (allSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        visibleIds.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelectedIds((prev) => new Set([...prev, ...visibleIds]));
    }
  }

  async function handleSingleDelete(id: string) {
    if (!window.confirm("Delete this transaction?")) return;
    setDeleting(true);
    try {
      const idToken = await getIdToken();
      await deleteTransaction(idToken, id);
      setTransactions((prev) => prev.filter((t) => t.id !== id));
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  async function handleBulkDelete() {
    if (selectedIds.size === 0) return;
    if (!window.confirm(`Delete ${selectedIds.size} selected transaction${selectedIds.size !== 1 ? "s" : ""}?`)) return;
    setDeleting(true);
    try {
      const idToken = await getIdToken();
      const ids = [...selectedIds];
      await bulkDeleteTransactions(idToken, ids);
      setTransactions((prev) => prev.filter((t) => !selectedIds.has(t.id)));
      setSelectedIds(new Set());
    } catch (err) {
      alert(err instanceof Error ? err.message : "Bulk delete failed");
    } finally {
      setDeleting(false);
    }
  }

  async function handleSave(id: string, req: TransactionUpdateRequest) {
    try {
      const idToken = await getIdToken();
      const updated = await updateTransaction(idToken, id, req);
      setTransactions((prev) => prev.map((t) => (t.id === id ? updated : t)));
      setEditingId(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Save failed");
    }
  }

  if (!user) {
    return (
      <main className="documents-page documents-page--centered">
        <p className="page-copy">Sign in to view financial transactions.</p>
      </main>
    );
  }

  const hasFilters = Object.values(filters).some(Boolean);

  return (
    <main className="documents-page">
      <div className="page-heading">
        <h1 className="page-title">Finances</h1>
        <p className="page-copy">
          Import bank statements, categorize transactions, and prepare for board reports.
        </p>
      </div>

      {!loadingDocs && (
        <ImportPanel csvDocuments={csvDocuments} onImported={() => void fetchTransactions()} />
      )}

      {!loadingTx && transactions.length > 0 && (
        <>
          <SummaryBar transactions={filtered} />

          <div className="fin-filters-row">
            <FilterBar
              filters={filters}
              onChange={(partial) => setFilters((f) => ({ ...f, ...partial }))}
              onClear={() => setFilters(EMPTY_FILTERS)}
              onAiCategorize={() => void handleAiCategorize()}
              aiCategorizing={aiCategorizing}
              aiResult={aiCategorizeResult}
            />
          </div>
        </>
      )}

      <div className="document-list">
        <div className="document-list__heading">
          <h2>Transactions{hasFilters ? " (filtered)" : ""}</h2>
          <span>
            {filtered.length !== transactions.length
              ? `${filtered.length} of ${transactions.length}`
              : `${transactions.length} total`}
            {transactions.filter((t) => !t.category || t.category === "Uncategorized").length > 0 && (
              <span style={{ marginLeft: 12, color: "#86631e" }}>
                · {transactions.filter((t) => !t.category || t.category === "Uncategorized").length} uncategorized
              </span>
            )}
          </span>
        </div>

        {selectedIds.size > 0 && (
          <div className="fin-bulk-toolbar">
            <span>{selectedIds.size} selected</span>
            <button
              className="table-action table-action--danger"
              type="button"
              disabled={deleting}
              onClick={() => void handleBulkDelete()}
            >
              {deleting ? "Deleting…" : `Delete ${selectedIds.size}`}
            </button>
            <button
              className="table-action table-action--muted"
              type="button"
              onClick={() => setSelectedIds(new Set())}
            >
              Clear selection
            </button>
          </div>
        )}

        {loadingTx ? (
          <p style={{ color: "#7a837f", fontSize: 13 }}>Loading…</p>
        ) : txError ? (
          <p className="document-error">{txError}</p>
        ) : transactions.length === 0 ? (
          <div className="empty-state">
            No transactions yet. Import a CSV document above to get started.
          </div>
        ) : (
          <TransactionTable
            transactions={sortedFiltered}
            editingId={editingId}
            onEdit={setEditingId}
            onSave={handleSave}
            onCancelEdit={() => setEditingId(null)}
            selectedIds={selectedIds}
            onToggleSelect={handleToggleSelect}
            onToggleAll={handleToggleAll}
            onSingleDelete={(id) => void handleSingleDelete(id)}
            sortCol={sortCol}
            sortDir={sortDir}
            onSort={handleSort}
          />
        )}
      </div>
    </main>
  );
}
