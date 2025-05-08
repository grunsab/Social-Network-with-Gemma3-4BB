import React, { createContext, useState, useContext, useEffect } from 'react';

// Create the context
const AuthContext = createContext(null);

// Create a provider component
export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true); // Start loading true
  const [unreadCount, setUnreadCount] = useState(0); // Add unreadCount state

  // Function to fetch unread notification count
  const fetchUnreadCount = async () => {
    try {
      const resp = await fetch('/api/v1/notifications/unread_count', { credentials: 'include' });
      if (resp.ok) {
        const data = await resp.json();
        setUnreadCount(data.unread_count || 0);
      }
    } catch (err) {
      console.error('Failed to fetch unread count in AuthContext', err);
      // Potentially set to 0 or handle error appropriately
      setUnreadCount(0);
    }
  };

  // Check for existing session on initial load
  useEffect(() => {
    const checkSession = async () => {
      try {
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
          fetchUnreadCount(); // Fetch count after session check
        } else {
          // If status is 401 or other error, assume not logged in
          setCurrentUser(null);
          setUnreadCount(0); // Reset count if not logged in
        }
      } catch (error) {
        console.error("Session check failed:", error);
        setCurrentUser(null);
        setUnreadCount(0); // Reset count on error
      } finally {
        setLoading(false); // Set loading false after check completes
      }
    };
    checkSession();
  }, []);

  // Function to handle login - expects user data from API
  const login = (userData) => {
    setCurrentUser(userData);
    fetchUnreadCount(); // Fetch count on login
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
    setUnreadCount(0); // Reset count on logout
    // TODO: Clear any stored token/session info
  };

  // Function to refresh user profile data
  const refreshUserProfile = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/profiles/me', { 
          method: 'GET',
          credentials: 'include'
      }); 
      if (response.ok) {
        const data = await response.json();
        const userData = data.user || data;
        setCurrentUser(userData);
        return true;
      }
      return false;
    } catch (error) {
      console.error("Profile refresh failed:", error);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const value = {
    currentUser,
    loading, // Expose loading state for initial check
    login,
    logout,
    refreshUserProfile, // Expose the refresh function
    unreadCount, // Expose unreadCount
    setUnreadCount, // Expose setUnreadCount
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