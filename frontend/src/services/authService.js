// Simple auth service for local storage management
class AuthService {
  getUserData() {
    const userData = localStorage.getItem('user_data');
    return userData ? JSON.parse(userData) : null;
  }

  getAuthToken() {
    return localStorage.getItem('auth_token');
  }

  isAuthenticated() {
    const token = this.getAuthToken();
    const userData = this.getUserData();
    return !!(token && userData);
  }

  clearAuth() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    document.cookie = 'user_data=; path=/; max-age=0';
    document.cookie = 'auth_token=; path=/; max-age=0';
  }
}

export const authService = new AuthService();