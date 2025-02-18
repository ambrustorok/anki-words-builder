import React from 'react';
import { Navigate } from 'react-router-dom';
import AuthService from '../services/auth.service';

const ProtectedRoute = ({ children }) => {
  const user = AuthService.getCurrentUser();

  if (!user) {
    // If no user is found in local storage, redirect to login page
    return <Navigate to="/login" />;
  }

  // If user is authenticated, render the child components
  return children;
};

export default ProtectedRoute;
