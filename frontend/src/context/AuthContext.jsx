import React, { createContext, useState, useContext, useEffect } from 'react';

// Create the context
const AuthContext = createContext(null);

// Create a provider component
export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true); // Start loading true

  // Check for existing session on initial load
  useEffect(() => {
    const checkSession = async () => {
      try {
        // Use the existing endpoint that requires login and returns user data
        const response = await fetch('/api/v1/profiles/me', { 
            method: 'GET', // Explicit GET is good practice
            credentials: 'include' // *** Add this to send cookies ***
        }); 
        if (response.ok) {
          const data = await response.json();
          console.log('AuthContext Session Check Response Data:', data); // Log API response
          // Check if user data is nested under 'user' key, otherwise assume it's top-level
          const userData = data.user || data;
          setCurrentUser(userData);
        } else {
          // If status is 401 or other error, assume not logged in
          setCurrentUser(null);
        }
      } catch (error) {
        console.error("Session check failed:", error);
        setCurrentUser(null);
      } finally {
        setLoading(false); // Set loading false after check completes
      }
    };
    checkSession();
    
    // Remove the previous assumption
    // setLoading(false); 
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