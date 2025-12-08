import { Language } from '../types/language';

// Base URL handling: Uses env var for production, defaults to localhost for dev
// Ensure NEXT_PUBLIC_API_URL is set in your frontend .env if deployment differs
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Generic wrapper for fetch requests with error handling
 */
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  // Default headers (can be overridden)
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const config = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      // Try to parse error message from JSON, fallback to status text
      let errorMessage = `API Error ${response.status}: ${response.statusText}`;
      try {
        const errorData = await response.json();
        if (errorData.detail) errorMessage = errorData.detail;
      } catch (e) {
        // Response wasn't JSON
      }
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error(`API Request Failed: ${endpoint}`, error);
    throw error;
  }
}

// ============================================================================
// LANGUAGE SERVICES
// ============================================================================

/**
 * Fetches the complete list of supported languages (RGL + Factory).
 * Usage: Returns the 300+ items for the LanguageSelector dropdown.
 */
export async function getLanguages(): Promise<Language[]> {
  // This hits the new endpoint added to main.py
  return request<Language[]>('/languages');
}

// ============================================================================
// SYSTEM SERVICES
// ============================================================================

/**
 * Checks if the backend is alive.
 */
export async function getHealth(): Promise<{ status: string; version: string }> {
  return request<{ status: string; version: string }>('/health');
}

// ============================================================================
// GENERATION SERVICES (Placeholders for existing logic)
// ============================================================================

/* * You can uncomment and adapt these as you integrate the rest of the 
 * frontend features with the new backend structure.
 */

// export async function generateText(payload: any) {
//   return request('/api/v1/generate', {
//     method: 'POST',
//     body: JSON.stringify(payload),
//   });
// }