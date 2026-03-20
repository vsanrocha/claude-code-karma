/**
 * Centralized configuration for Claude Code Karma frontend.
 *
 * API Base URL:
 * - Uses PUBLIC_API_URL environment variable if set (process.env, read at runtime)
 * - Falls back to http://localhost:8000 for local development
 *
 * To configure in production:
 * - Set PUBLIC_API_URL in your deployment environment
 * - Or set it in your .env file
 */
import { env } from '$env/dynamic/public';

/**
 * API base URL for all backend requests.
 * @example
 * ```ts
 * import { API_BASE } from '$lib/config';
 * const response = await fetch(`${API_BASE}/projects`);
 * ```
 */
export const API_BASE = env.PUBLIC_API_URL || 'http://localhost:8000';

/**
 * API request timeout in milliseconds (default: 30 seconds)
 */
export const API_TIMEOUT = 30_000;

/**
 * Polling intervals for real-time data
 */
export const POLLING_INTERVALS = {
	/** Live sessions polling interval (ms) */
	LIVE_SESSIONS: 2_000,
	/** Historical data polling interval (ms) */
	HISTORICAL_DATA: 30_000
} as const;
