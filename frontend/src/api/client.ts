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
  ShareResponse,
  Transaction,
  TransactionCreateRequest,
  TransactionUpdateRequest,
  TransactionUploadCsvRequest,
  TransactionUploadCsvResponse,
  UserSettings,
  UserSettingsUpdateRequest,
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
    const { detail } = body;
    if (typeof detail === "string") return detail;
    // Object detail: { message, warnings }
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const d = detail as Record<string, unknown>;
      const parts: string[] = [];
      if (typeof d.message === "string") parts.push(d.message);
      if (Array.isArray(d.warnings) && d.warnings.length > 0) {
        parts.push(...(d.warnings as string[]).slice(0, 5));
      }
      if (parts.length) return parts.join("\n");
    }
    // FastAPI validation error: array of { loc, msg, type }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as Record<string, unknown>;
      if (typeof first.msg === "string") return `Validation error: ${first.msg}`;
    }
    return fallbackMessage;
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

export async function shareReview(
  idToken: string,
  contractId: string,
): Promise<ShareResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/contracts/${contractId}/review/share`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${idToken}` },
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not generate share link"));
  }

  return response.json() as Promise<ShareResponse>;
}

export async function shareComparison(
  idToken: string,
  comparisonId: string,
): Promise<ShareResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/contracts/comparisons/${comparisonId}/share`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${idToken}` },
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not generate share link"));
  }

  return response.json() as Promise<ShareResponse>;
}

export async function getSharedReview(
  token: string,
  signal?: AbortSignal,
): Promise<ContractWithReview> {
  const response = await fetch(`${API_BASE_URL}/api/v1/shared/review/${token}`, { signal });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Shared review not found"));
  }

  return response.json() as Promise<ContractWithReview>;
}

export async function getSharedComparison(
  token: string,
  signal?: AbortSignal,
): Promise<ContractCompareResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/shared/comparison/${token}`, { signal });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Shared comparison not found"));
  }

  return response.json() as Promise<ContractCompareResponse>;
}

export async function uploadCsvTransactions(
  idToken: string,
  request: TransactionUploadCsvRequest,
): Promise<TransactionUploadCsvResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/financials/transactions/upload-csv`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${idToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "CSV import failed"));
  }

  return response.json() as Promise<TransactionUploadCsvResponse>;
}

export async function createTransaction(
  idToken: string,
  request: TransactionCreateRequest,
): Promise<Transaction> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/financials/transactions`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${idToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not create transaction"));
  }

  return response.json() as Promise<Transaction>;
}

export async function listTransactions(
  idToken: string,
  params?: { date_from?: string; date_to?: string },
  signal?: AbortSignal,
): Promise<Transaction[]> {
  const url = new URL(`${API_BASE_URL}/api/v1/financials/transactions`);
  if (params?.date_from) url.searchParams.set("date_from", params.date_from);
  if (params?.date_to) url.searchParams.set("date_to", params.date_to);

  const response = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${idToken}` },
    signal,
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load transactions"));
  }

  return response.json() as Promise<Transaction[]>;
}

export async function deleteTransaction(
  idToken: string,
  transactionId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/financials/transactions/${transactionId}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${idToken}` },
    },
  );
  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not delete transaction"));
  }
}

export async function bulkDeleteTransactions(
  idToken: string,
  ids: string[],
): Promise<{ deleted_count: number }> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/financials/transactions/bulk-delete`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${idToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ids }),
    },
  );
  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not delete transactions"));
  }
  return response.json() as Promise<{ deleted_count: number }>;
}

export async function updateTransaction(
  idToken: string,
  transactionId: string,
  request: TransactionUpdateRequest,
): Promise<Transaction> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/financials/transactions/${transactionId}`,
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
    throw new Error(await errorDetail(response, "Could not update transaction"));
  }

  return response.json() as Promise<Transaction>;
}

export async function aiCategorizeTransactions(
  idToken: string,
): Promise<{ updated_count: number; skipped_count: number }> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/financials/transactions/ai-categorize`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${idToken}` },
    },
  );
  if (!response.ok) {
    throw new Error(await errorDetail(response, "AI categorization failed"));
  }
  return response.json() as Promise<{ updated_count: number; skipped_count: number }>;
}

export async function getUserSettings(idToken: string): Promise<UserSettings> {
  const response = await fetch(`${API_BASE_URL}/api/v1/settings`, {
    headers: { Authorization: `Bearer ${idToken}` },
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not load settings"));
  }

  return response.json() as Promise<UserSettings>;
}

export async function updateUserSettings(
  idToken: string,
  request: UserSettingsUpdateRequest,
): Promise<UserSettings> {
  const response = await fetch(`${API_BASE_URL}/api/v1/settings`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(await errorDetail(response, "Could not update settings"));
  }

  return response.json() as Promise<UserSettings>;
}
