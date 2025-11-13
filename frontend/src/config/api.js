// API configuration for different environments
const getApiBaseUrl = () => {
  // In production, use relative URLs since nginx handles routing
  if (process.env.NODE_ENV === 'production') {
    return '';
  }
  
  // In development, use localhost
  return 'http://localhost:8000';
};

export const API_BASE_URL = getApiBaseUrl();

// API endpoints
export const API_ENDPOINTS = {
  AUTH_VALIDATE: `${API_BASE_URL}/auth/validate`,
  AUTH_GOOGLE: `${API_BASE_URL}/auth/google`,
  AUTH_LOGOUT: `${API_BASE_URL}/auth/logout`,
};