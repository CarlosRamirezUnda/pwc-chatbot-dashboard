/**
 * Backend API base URL for all fetch calls.
 * Priority: VITE_API_URL env → production default → local dev default.
 */
const PRODUCTION_API_URL = 'https://pwc-chatbot-dashboard.onrender.com';

export const API_URL = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? PRODUCTION_API_URL : 'http://localhost:8000')
).replace(/\/$/, '');
