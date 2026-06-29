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

export interface ContractReviewRequest {
  document_id: string;
  vendor_name?: string;
  contract_type?: string;
}

export interface Contract {
  id: string;
  organization_id: string;
  document_id: string;
  vendor_name: string | null;
  contract_type: string | null;
  status: string;
  created_at: string;
}

export interface ContractRubricScore {
  id: string;
  category: string;
  score: number;
  max_score: number;
  explanation: string;
  citation: string | null;
}

export interface ContractRiskFlag {
  id: string;
  risk_type: string;
  severity: string;
  explanation: string;
  citation: string | null;
  suggested_fix: string | null;
}

export interface ContractReview {
  id: string;
  contract_id: string;
  model_name: string;
  flow_name: string;
  total_score: number;
  risk_level: string;
  executive_summary: string;
  recommendation: string;
  rubric_scores: ContractRubricScore[];
  risk_flags: ContractRiskFlag[];
  created_at: string;
}

export interface ContractWithReview {
  contract: Contract;
  review: ContractReview;
}
