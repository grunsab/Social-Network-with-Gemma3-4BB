// src/App.test.jsx
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';

import App from './App';
// Mock the AuthContext or provide a mock implementation
// For simplicity, let's assume a basic mock provider structure
import { AuthProvider } from './context/AuthContext'; // Adjust import path if needed

// Mock implementation (replace with your actual context structure if different)
// This basic mock assumes AuthProvider takes children and provides
// a context value with { currentUser: null, loading: false, logout: () => {} }
// You might need a more sophisticated mock depending on AuthContext's implementation
const MockAuthProvider = ({ children }) => (
  <AuthProvider value={{ currentUser: null, loading: false, logout: () => {} }}>
    {children}
  </AuthProvider>
);

describe('App Component', () => {
  it('renders Login and Register links when not logged in', () => {
    render(
      <MockAuthProvider>
          <App />
      </MockAuthProvider>
    );

    // Check for the main title/link
    expect(screen.getByRole('link', { name: /socialnet/i })).toBeInTheDocument();

    // Check for Login and Register links *within the nav*
    const nav = screen.getByRole('navigation'); // Find the <nav> element
    expect(within(nav).getByRole('link', { name: /login/i })).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: /register/i })).toBeInTheDocument();

    // Ensure Dashboard/Profile links are NOT present
    expect(screen.queryByRole('link', { name: /dashboard/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /my profile/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /logout/i })).not.toBeInTheDocument();
  });

  // TODO: Add tests for logged-in state
}); 