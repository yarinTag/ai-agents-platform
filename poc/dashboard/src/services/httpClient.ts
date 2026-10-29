import axios from 'axios';

export const AUTH_TOKEN_KEY = 'agents_platform_auth_token';
export const AUTH_SESSION_KEY = 'agents_platform_auth_session';

const API_BASE_URL = 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// Axios Request Interceptor: Attach Bearer token from localStorage
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (token) {
      if (config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Axios Response Interceptor: Catch 401 and broadcast auth:unauthorized
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      const isAuthExempt =
        url.includes('/auth/login') ||
        url.includes('/auth/org-register') ||
        url.includes('/invitations/accept');

      if (!isAuthExempt) {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(AUTH_SESSION_KEY);
        window.dispatchEvent(new CustomEvent('auth:unauthorized'));
      }
    }
    return Promise.reject(error);
  }
);

export default api;
