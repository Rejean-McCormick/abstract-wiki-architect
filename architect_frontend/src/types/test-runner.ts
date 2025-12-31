export interface TestDefinition {
  /**
   * Unique identifier for the test (defaults to filename if missing in JSON)
   */
  id: string;

  /**
   * Display name in the dropdown menu
   */
  label: string;

  /**
   * Optional helper text displayed below the dropdown
   */
  description?: string;

  /**
   * HTTP Method
   */
  method: "GET" | "POST" | "PUT" | "DELETE";

  /**
   * API Endpoint (e.g. "/generate" or "/health/ready")
   */
  endpoint: string;

  /**
   * Optional custom headers (e.g. specific auth tokens for this test)
   */
  headers?: Record<string, string>;

  /**
   * JSON body for POST/PUT requests
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any;
}