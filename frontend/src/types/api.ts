export interface ApiError {
  detail?: string;
  message?: string;
  [key: string]: unknown;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
