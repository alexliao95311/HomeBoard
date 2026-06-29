import type {
  AuthenticatedUser,
  Contract,
  ContractCompareRequest,
  ContractCompareResponse,
  ContractComparisonListItem,
  ContractReview,
  ContractReviewRequest,
  ContractReviewUpdateRequest,
  ContractUpdateRequest,
  ContractWithReview,
  Document,
  DocumentProcessResult,
  DocumentTextChunk,
  DocumentType,
  DocumentUpdateRequest,
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

export async function updateDocument(
  idToken: string,
  documentId: string,
  request: DocumentUpdateRequest,
): Promise<Document> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not update document"));
  }

  return response.json() as Promise<Document>;
}

export async function deleteDocument(
  idToken: string,
  documentId: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${idToken}` },
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not delete document"));
  }
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

export async function reviewContract(
  idToken: string,
  request: ContractReviewRequest,
): Promise<ContractWithReview> {
  const response = await fetch(`${API_BASE_URL}/api/v1/contracts/review`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Contract review failed"));
  }

  return response.json() as Promise<ContractWithReview>;
}

export async function getContract(
  idToken: string,
  contractId: string,
  signal?: AbortSignal,
): Promise<Contract> {
  const response = await fetch(`${API_BASE_URL}/api/v1/contracts/${contractId}`, {
    headers: { Authorization: `Bearer ${idToken}` },
    signal,
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load contract"));
  }

  return response.json() as Promise<Contract>;
}

export async function listContracts(
  idToken: string,
  signal?: AbortSignal,
): Promise<Contract[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/contracts`, {
    headers: { Authorization: `Bearer ${idToken}` },
    signal,
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load contracts"));
  }

  return response.json() as Promise<Contract[]>;
}

export async function getContractReview(
  idToken: string,
  contractId: string,
  signal?: AbortSignal,
): Promise<ContractReview> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/contracts/${contractId}/review`,
    {
      headers: { Authorization: `Bearer ${idToken}` },
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load contract review"));
  }

  return response.json() as Promise<ContractReview>;
}

export async function updateContract(
  idToken: string,
  contractId: string,
  request: ContractUpdateRequest,
): Promise<Contract> {
  const response = await fetch(`${API_BASE_URL}/api/v1/contracts/${contractId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not update contract"));
  }

  return response.json() as Promise<Contract>;
}

export async function updateContractReview(
  idToken: string,
  contractId: string,
  request: ContractReviewUpdateRequest,
): Promise<ContractReview> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/contracts/${contractId}/review`,
    {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${idToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not update review"));
  }

  return response.json() as Promise<ContractReview>;
}

export async function deleteContract(
  idToken: string,
  contractId: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/contracts/${contractId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${idToken}` },
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not delete contract"));
  }
}

export async function compareContracts(
  idToken: string,
  request: ContractCompareRequest,
): Promise<ContractCompareResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/contracts/compare`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Contract comparison failed"));
  }

  return response.json() as Promise<ContractCompareResponse>;
}

export async function listComparisons(
  idToken: string,
  signal?: AbortSignal,
): Promise<ContractComparisonListItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/contracts/comparisons`, {
    headers: { Authorization: `Bearer ${idToken}` },
    signal,
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load comparisons"));
  }

  return response.json() as Promise<ContractComparisonListItem[]>;
}

export async function getComparison(
  idToken: string,
  comparisonId: string,
  signal?: AbortSignal,
): Promise<ContractCompareResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/contracts/comparisons/${comparisonId}`,
    {
      headers: { Authorization: `Bearer ${idToken}` },
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load comparison"));
  }

  return response.json() as Promise<ContractCompareResponse>;
}

export async function deleteComparison(
  idToken: string,
  comparisonId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/contracts/comparisons/${comparisonId}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${idToken}` },
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not delete comparison"));
  }
}
