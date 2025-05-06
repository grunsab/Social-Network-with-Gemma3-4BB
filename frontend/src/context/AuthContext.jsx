import React, { createContext, useState, useContext, useEffect } from 'react';

// Create the context
const AuthContext = createContext(null);

// Create a provider component
export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true); // Track initial loading state

  // TODO: Check for existing session/token on initial load (e.g., from localStorage or httpOnly cookie check)
  useEffect(() => {
    // Example: Placeholder for checking session
    // const checkSession = async () => {
    //   try {
    //     const response = await fetch('/api/v1/session/check'); // Hypothetical endpoint
    //     if (response.ok) {
    //       const user = await response.json();
    //       setCurrentUser(user);
    //     } else {
    //       setCurrentUser(null);
    //     }
    //   } catch (error) {
    //     console.error("Session check failed:", error);
    //     setCurrentUser(null);
    //   } finally {
    //     setLoading(false);
    //   }
    // };
    // checkSession();
    
    // For now, assume no session on load
    setLoading(false); 
  }, []);

  // Function to handle login - expects user data from API
  const login = (userData) => {
    setCurrentUser(userData);
    // TODO: Maybe store token or session info if applicable
  };

  // Function to handle logout
  const logout = async () => {
    // Call the backend logout endpoint
    try {
      const response = await fetch('/api/v1/login', { method: 'DELETE' }); // Uses DELETE on /api/v1/login
      if (!response.ok) {
         // Handle error, though frontend state is cleared anyway
         const data = await response.json();
         console.error("Logout failed on backend:", data.message);
      } 
    } catch (error) {
       console.error("Logout API call failed:", error);
    }
    setCurrentUser(null);
    // TODO: Clear any stored token/session info
  };

  const value = {
    currentUser,
    loading, // Expose loading state for initial check
    login,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children} 
    </AuthContext.Provider>
  );
};

// Custom hook to use the auth context
export const useAuth = () => {
  return useContext(AuthContext);
}; 