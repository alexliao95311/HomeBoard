export interface HealthResponse {
  status: "healthy";
  service: string;
  environment: string;
  timestamp: string;
}
