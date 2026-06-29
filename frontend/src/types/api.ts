export interface HealthResponse {
  status: "ok";
}

export interface AuthenticatedUser {
  uid: string;
  email: string | null;
  name: string | null;
  picture: string | null;
  email_verified: boolean;
}

export type DocumentType =
  | "contract"
  | "bank_statement"
  | "budget"
  | "invoice"
  | "other";

export interface Document {
  id: string;
  organization_id: string;
  uploaded_by_id: string;
  document_type: string;
  status: "uploaded" | string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface DocumentTextChunk {
  id: string;
  document_id: string;
  page_number: number | null;
  chunk_index: number;
  text: string;
  created_at: string;
}

export interface DocumentProcessResult {
  document_id: string;
  status: string;
  chunk_count: number;
}
