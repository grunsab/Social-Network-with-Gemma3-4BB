import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = () => {
  const { currentUser, loading } = useAuth();

  if (loading) {
    // Optionally, show a loading spinner while checking auth status
    return <div>Loading...</div>; 
  }

  // If user is authenticated, render the child route element
  // Outlet is a placeholder for the nested route component
  return currentUser ? <Outlet /> : <Navigate to="/login" replace />;
};

export default ProtectedRoute; 