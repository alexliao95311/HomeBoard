import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getDocument,
  getDocumentText,
  processDocument,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { Document, DocumentTextChunk } from "../types/api";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentTextPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const { user, loading: authLoading, signInWithGoogle, getIdToken } = useAuth();
  const [document, setDocument] = useState<Document | null>(null);
  const [chunks, setChunks] = useState<DocumentTextChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDocument = useCallback(
    async (signal?: AbortSignal) => {
      if (!documentId) throw new Error("Document ID is missing");
      const token = await getIdToken();
      const [metadata, extractedText] = await Promise.all([
        getDocument(token, documentId, signal),
        getDocumentText(token, documentId, signal),
      ]);
      setDocument(metadata);
      setChunks(extractedText);
    },
    [documentId, getIdToken],
  );

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loadDocument(controller.signal)
      .catch((loadError: unknown) => {
        if (
          loadError instanceof DOMException &&
          loadError.name === "AbortError"
        ) {
          return;
        }
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Could not load document",
        );
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [user, loadDocument]);

  async function handleProcess() {
    if (!documentId) return;
    setProcessing(true);
    setError(null);
    try {
      const token = await getIdToken();
      await processDocument(token, documentId);
      await loadDocument();
    } catch (processError) {
      setError(
        processError instanceof Error
          ? processError.message
          : "Document processing failed",
      );
      await loadDocument().catch(() => undefined);
    } finally {
      setProcessing(false);
    }
  }

  if (authLoading || loading) {
    return <main className="documents-page">Loading document…</main>;
  }

  if (!user) {
    return (
      <main className="documents-page documents-page--centered">
        <p className="eyebrow">Document text</p>
        <h1 className="page-title">Sign in to view this document.</h1>
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
      <Link className="back-link" to="/documents">
        ← Back to documents
      </Link>

      {document ? (
        <>
          <div className="document-detail-heading">
            <div>
              <p className="eyebrow">Extracted document text</p>
              <h1 className="detail-title">{document.original_filename}</h1>
              <div className="document-meta">
                <span>{document.document_type.replaceAll("_", " ")}</span>
                <span>{formatBytes(document.size_bytes)}</span>
                <span className={`status-pill status-pill--${document.status}`}>
                  {document.status}
                </span>
              </div>
            </div>
            <button
              className="button button--primary"
              type="button"
              disabled={processing}
              onClick={() => void handleProcess()}
            >
              {processing
                ? "Processing…"
                : document.status === "processed"
                  ? "Process again"
                  : document.status === "failed"
                    ? "Retry processing"
                    : "Process document"}
            </button>
          </div>

          {error ? (
            <div className="document-error" role="alert">
              {error}
            </div>
          ) : null}

          <section className="text-chunks" aria-labelledby="chunks-heading">
            <div className="document-list__heading">
              <h2 id="chunks-heading">Text chunks</h2>
              <span>{chunks.length} total</span>
            </div>
            {chunks.length === 0 ? (
              <p className="empty-state">
                {document.status === "failed"
                  ? "Extraction failed. Retry processing or check the source file."
                  : "Process this document to extract its text."}
              </p>
            ) : (
              chunks.map((chunk) => (
                <article className="text-chunk" key={chunk.id}>
                  <header>
                    <span>Chunk {chunk.chunk_index + 1}</span>
                    {chunk.page_number ? (
                      <span>Page {chunk.page_number}</span>
                    ) : null}
                  </header>
                  <pre>{chunk.text}</pre>
                </article>
              ))
            )}
          </section>
        </>
      ) : (
        <div className="document-error" role="alert">
          {error ?? "Document not found"}
        </div>
      )}
    </main>
  );
}
