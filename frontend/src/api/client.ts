import type {
  AuthenticatedUser,
  Document,
  DocumentProcessResult,
  DocumentTextChunk,
  DocumentType,
  HealthResponse,
} from "../types/api";

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, { signal });

  if (!response.ok) {
    throw new Error(`API health check failed with status ${response.status}`);
  }

  return response.json() as Promise<HealthResponse>;
}

export async function getCurrentUser(
  idToken: string,
): Promise<AuthenticatedUser> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${idToken}` },
  });

  if (!response.ok) {
    throw new Error("The backend could not verify your Google account");
  }

  return response.json() as Promise<AuthenticatedUser>;
}

async function errorDetail(
  response: Response,
  fallbackMessage: string,
): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}

export async function uploadDocument(
  idToken: string,
  file: File,
  documentType: DocumentType,
): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);

  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Document upload failed"));
  }

  return response.json() as Promise<Document>;
}

export async function listDocuments(
  idToken: string,
  signal?: AbortSignal,
): Promise<Document[]> {
  const response = await fetch(`${API_BASE_URL}/documents`, {
    headers: { Authorization: `Bearer ${idToken}` },
    signal,
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load documents"));
  }

  return response.json() as Promise<Document[]>;
}

export async function getDocument(
  idToken: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<Document> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
    headers: { Authorization: `Bearer ${idToken}` },
    signal,
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load document"));
  }

  return response.json() as Promise<Document>;
}

export async function processDocument(
  idToken: string,
  documentId: string,
): Promise<DocumentProcessResult> {
  const response = await fetch(
    `${API_BASE_URL}/documents/${documentId}/process`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${idToken}` },
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Document processing failed"));
  }

  return response.json() as Promise<DocumentProcessResult>;
}

export async function getDocumentText(
  idToken: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentTextChunk[]> {
  const response = await fetch(
    `${API_BASE_URL}/documents/${documentId}/text`,
    {
      headers: { Authorization: `Bearer ${idToken}` },
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load document text"));
  }

  return response.json() as Promise<DocumentTextChunk[]>;
}
