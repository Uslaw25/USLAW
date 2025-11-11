import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      // Check if we have valid session with FastAPI wrapper
      const response = await fetch('http://localhost:8000/auth/validate', {
        method: 'GET',
        credentials: 'include', // Include cookies
      });
      
      const data = await response.json();
      
      if (data.valid) {
        // Get user data from localStorage if available
        const savedUserData = localStorage.getItem('user_data');
        if (savedUserData) {
          setUser(JSON.parse(savedUserData));
        }
      } else {
        // Clear any stale data
        logout();
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (googleCredentialResponse) => {
    try {
      setLoading(true);
      
      // Send Google credential to FastAPI wrapper endpoint
      const response = await fetch('http://localhost:8000/auth/google', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Essential for cookies
        body: JSON.stringify({
          credential: googleCredentialResponse.credential
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Authentication failed');
      }
      
      const data = await response.json();
      
      if (data.success) {
        // Store user data locally for React UI
        localStorage.setItem('user_data', JSON.stringify(data.user));
        setUser(data.user);
        
        // Cookies are automatically set by FastAPI wrapper using _authenticate_user()
        return data;
      } else {
        throw new Error('Authentication failed');
      }
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      // Call logout endpoint to clear httpOnly cookies
      await fetch('http://localhost:8000/auth/logout', {
        method: 'POST',
        credentials: 'include', // Include cookies for clearing
      });
    } catch (error) {
      console.error('Logout API call failed:', error);
      // Continue with local cleanup even if API fails
    }
    
    // Clear local storage
    localStorage.removeItem('user_data');
    setUser(null);
  };

  const value = {
    user,
    loading,
    login,
    logout,
    checkAuthStatus
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};