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

export interface DocumentUpdateRequest {
  original_filename: string;
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

export interface BoardQuestion {
  question: string;
  section: string | null;
}

export interface NegotiationPoint {
  point: string;
  section: string | null;
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
  board_questions: BoardQuestion[];
  negotiation_points: NegotiationPoint[];
  created_at: string;
}

export interface ContractWithReview {
  contract: Contract;
  review: ContractReview;
}

export interface ContractUpdateRequest {
  vendor_name?: string | null;
  contract_type?: string | null;
}

export interface ContractReviewUpdateRequest {
  executive_summary?: string;
  recommendation?: string;
  risk_level?: "low" | "medium" | "high";
  total_score?: number;
}

export interface ContractCompareRequest {
  contract_ids: string[];
}

export interface RankedContract {
  rank: number;
  contract_id: string;
  vendor_name: string | null;
  contract_type: string | null;
  total_score: number;
  risk_level: string;
}

export interface SideBySideRow {
  category: string;
  scores: { [contractId: string]: number };
  max_score: number;
}

export interface AiPerContractNote {
  contract_id: string;
  strengths: string[];
  weaknesses: string[];
  verdict: string;
}

export interface ContractCompareResponse {
  comparison_id: string;
  ai_summary: string;
  ai_model: string;
  ai_per_contract: AiPerContractNote[];
  ai_critical_differences: string[];
  ranked_contracts: RankedContract[];
  side_by_side_table: SideBySideRow[];
  best_overall: string;
  lowest_risk: string;
  best_value: string;
  key_differences: string[];
}

export interface ContractComparisonListItem {
  id: string;
  vendor_names: string[];
  ai_model: string;
  best_overall_vendor: string | null;
  created_at: string;
}

export interface ShareResponse {
  token: string;
}

export interface UserSettings {
  preferred_model: string;
}

export interface UserSettingsUpdateRequest {
  preferred_model: string;
}

export const AI_MODELS = [
  { id: "openai/gpt-4o", label: "GPT-4o", provider: "OpenAI" },
  { id: "anthropic/claude-sonnet-5", label: "Claude Sonnet 5", provider: "Anthropic" },
  { id: "google/gemini-3.5-flash", label: "Gemini 3.5 Flash", provider: "Google" },
  { id: "x-ai/grok-4.3", label: "Grok 4.3", provider: "xAI" },
] as const;
