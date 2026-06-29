import {
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link } from "react-router-dom";

import {
  deleteDocument,
  listDocuments,
  processDocument,
  updateDocument,
  uploadDocument,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { Document, DocumentType } from "../types/api";

const documentTypes: Array<{ value: DocumentType; label: string }> = [
  { value: "contract", label: "Contract" },
  { value: "bank_statement", label: "Bank statement" },
  { value: "budget", label: "Budget" },
  { value: "invoice", label: "Invoice" },
  { value: "other", label: "Other" },
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDocumentType(documentType: string): string {
  return documentType.replaceAll("_", " ");
}

function DocumentRow({
  document,
  onDelete,
  onUpdate,
}: {
  document: Document;
  onDelete: (id: string) => void;
  onUpdate: (updated: Document) => void;
}) {
  const { getIdToken } = useAuth();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editName, setEditName] = useState("");

  function startEditing(e: React.MouseEvent) {
    e.stopPropagation();
    setEditName(document.original_filename);
    setEditing(true);
  }

  async function handleSave(e: React.MouseEvent) {
    e.stopPropagation();
    if (!editName.trim()) return;
    setSaving(true);
    try {
      const token = await getIdToken();
      const updated = await updateDocument(token, document.id, {
        original_filename: editName.trim(),
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
    onDelete(document.id);
  }

  return (
    <tr>
      <td>
        {editing ? (
          <input
            className="row-edit-input"
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            autoFocus
          />
        ) : (
          <>
            <Link
              className="document-name document-name--link"
              to={`/documents/${document.id}`}
            >
              {document.original_filename}
            </Link>
            <span className="document-hash">
              SHA-256 {document.sha256.slice(0, 12)}…
            </span>
          </>
        )}
      </td>
      <td className="capitalize">{formatDocumentType(document.document_type)}</td>
      <td>{formatBytes(document.size_bytes)}</td>
      <td>
        <span className="status-pill">{document.status}</span>
      </td>
      <td>
        {new Intl.DateTimeFormat(undefined, {
          dateStyle: "medium",
          timeStyle: "short",
        }).format(new Date(document.created_at))}
      </td>
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
            <Link
              className="table-action"
              to={`/documents/${document.id}`}
            >
              {document.status === "processed" ? "View text" : "View"}
            </Link>
            <button
              type="button"
              className="table-action"
              onClick={startEditing}
            >
              Rename
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

export function DocumentsPage() {
  const { user, loading: authLoading, signInWithGoogle, getIdToken } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [documentType, setDocumentType] =
    useState<DocumentType>("contract");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [listLoading, setListLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<"uploading" | "processing" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const refreshDocuments = useCallback(
    async (signal?: AbortSignal) => {
      setListLoading(true);
      try {
        const token = await getIdToken();
        setDocuments(await listDocuments(token, signal));
      } finally {
        setListLoading(false);
      }
    },
    [getIdToken],
  );

  useEffect(() => {
    if (!user) {
      setDocuments([]);
      return;
    }

    const controller = new AbortController();
    setError(null);
    refreshDocuments(controller.signal).catch((loadError: unknown) => {
      if (loadError instanceof DOMException && loadError.name === "AbortError") {
        return;
      }
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Could not load documents",
      );
    });
    return () => controller.abort();
  }, [user, refreshDocuments]);

  async function handleDelete(documentId: string) {
    if (
      !window.confirm(
        "Permanently delete this document? This cannot be undone.",
      )
    )
      return;

    try {
      const token = await getIdToken();
      await deleteDocument(token, documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
    } catch (deleteError) {
      setError(
        deleteError instanceof Error ? deleteError.message : "Delete failed",
      );
    }
  }

  function handleUpdate(updated: Document) {
    setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setError("Choose a file to upload");
      return;
    }

    setUploadLoading(true);
    setUploadStatus("uploading");
    setError(null);
    try {
      const token = await getIdToken();
      const doc = await uploadDocument(token, selectedFile, documentType);
      setUploadStatus("processing");
      await processDocument(token, doc.id);
      setSelectedFile(null);
      if (fileInput.current) fileInput.current.value = "";
      await refreshDocuments();
    } catch (uploadError) {
      setError(
        uploadError instanceof Error ? uploadError.message : "Upload failed",
      );
    } finally {
      setUploadLoading(false);
      setUploadStatus(null);
    }
  }

  if (authLoading) {
    return <main className="documents-page">Checking your account…</main>;
  }

  if (!user) {
    return (
      <main className="documents-page documents-page--centered">
        <p className="eyebrow">Document workspace</p>
        <h1 className="page-title">Sign in to manage HOA documents.</h1>
        <p className="page-copy">
          Documents are private and scoped to your organization.
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
          <p className="eyebrow">Document workspace</p>
          <h1 className="page-title">Upload and organize documents.</h1>
        </div>
        <p className="page-copy">
          PDF, CSV, DOCX, or XLSX. Maximum file size 25 MB.
        </p>
      </div>

      <section className="upload-panel" aria-labelledby="upload-heading">
        <div>
          <h2 id="upload-heading">Upload a document</h2>
          <p>Files are securely separated by organization.</p>
        </div>
        <form className="upload-form" onSubmit={handleUpload}>
          <label>
            Document type
            <select
              value={documentType}
              onChange={(event) =>
                setDocumentType(event.target.value as DocumentType)
              }
              disabled={uploadLoading}
            >
              {documentTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            File
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.csv,.docx,.xlsx,application/pdf,text/csv,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) =>
                setSelectedFile(event.target.files?.[0] ?? null)
              }
              disabled={uploadLoading}
            />
          </label>
          <button
            className="button button--primary"
            type="submit"
            disabled={uploadLoading}
          >
            {uploadStatus === "uploading"
              ? "Uploading…"
              : uploadStatus === "processing"
                ? "Processing…"
                : "Upload document"}
          </button>
        </form>
      </section>

      {error ? (
        <div className="document-error" role="alert">
          {error}
        </div>
      ) : null}

      <section className="document-list" aria-labelledby="documents-heading">
        <div className="document-list__heading">
          <h2 id="documents-heading">Uploaded documents</h2>
          <span>{documents.length} total</span>
        </div>

        {listLoading ? (
          <p className="empty-state">Loading documents…</p>
        ) : documents.length === 0 ? (
          <p className="empty-state">
            No documents yet. Upload the first file for your organization.
          </p>
        ) : (
          <div className="document-table-wrap">
            <table className="document-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Type</th>
                  <th>Size</th>
                  <th>Status</th>
                  <th>Uploaded</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => (
                  <DocumentRow
                    key={document.id}
                    document={document}
                    onDelete={(id) => void handleDelete(id)}
                    onUpdate={handleUpdate}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
