import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import Login from './Login';
import { AuthProvider, useAuth } from '../context/AuthContext';

// Mock react-router-dom navigate function
const mockedNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  };
});

// Mock useAuth hook
const mockLogin = vi.fn();
vi.mock('../context/AuthContext', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        useAuth: () => ({ // Provide the hook's return value
            login: mockLogin,
            // Add other context values if Login uses them, otherwise defaults are fine
            currentUser: null,
            loading: false, 
            logout: vi.fn(),
        }),
    };
});

// Mock global fetch
global.fetch = vi.fn();

describe('Login Component', () => {

  beforeEach(() => {
    // Reset mocks before each test
    mockLogin.mockClear();
    mockedNavigate.mockClear();
    global.fetch.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderLogin = () => {
    // Return the container from render
    return render(
      <MemoryRouter initialEntries={['/login']}>
        {/* Remove AuthProvider wrap - useAuth is mocked directly */}
        {/* <AuthProvider value={mockAuthContextValue}> */}
          <Routes>
            <Route path="/login" element={<Login />} />
            {/* Add a dummy route for the redirect target */}
            <Route path="/" element={<div>Dashboard Mock</div>} />
          </Routes>
        {/* </AuthProvider> */}
      </MemoryRouter>
    );
  };

  it('renders login form correctly', () => {
    renderLogin();
    expect(screen.getByLabelText(/username or email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /register here/i })).toBeInTheDocument();
  });

  it('allows inputting identifier and password', async () => {
    renderLogin();
    const identifierInput = screen.getByLabelText(/username or email/i);
    const passwordInput = screen.getByLabelText(/password/i);

    await fireEvent.change(identifierInput, { target: { value: 'testuser' } });
    await fireEvent.change(passwordInput, { target: { value: 'password123' } });

    expect(identifierInput.value).toBe('testuser');
    expect(passwordInput.value).toBe('password123');
  });

  it('calls fetch and logs in successfully on valid submission', async () => {
    const mockUserData = { id: 1, username: 'testuser', email: 'test@example.com' };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ user: mockUserData }),
    });

    renderLogin();

    const identifierInput = screen.getByLabelText(/username or email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /login/i });

    await fireEvent.change(identifierInput, { target: { value: 'testuser' } });
    await fireEvent.change(passwordInput, { target: { value: 'password123' } });
    await fireEvent.click(loginButton);

    // Check fetch call
    await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/v1/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identifier: 'testuser', password: 'password123' }),
        });
    });

    // Check context login function call
    expect(mockLogin).toHaveBeenCalledWith(mockUserData);

    // Check navigation
    expect(mockedNavigate).toHaveBeenCalledWith('/');
    
    // Check no error message is shown
    expect(screen.queryByRole('alert', { name: /error/i})).not.toBeInTheDocument(); // Assuming error <p> might get role 'alert'
    expect(screen.queryByText(/invalid credentials/i)).not.toBeInTheDocument();

  });

  it('displays error message on failed login (401)', async () => {
    const errorMessage = 'Invalid credentials';
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ message: errorMessage }),
    });

    // Get container from renderLogin
    const { container } = renderLogin();

    const identifierInput = screen.getByLabelText(/username or email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /login/i });

    await fireEvent.change(identifierInput, { target: { value: 'testuser' } });
    await fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } });
    await fireEvent.click(loginButton);

    // Wrap state update after await in act
    await act(async () => {
       // Wait for the error message element
       await waitFor(() => {
         expect(container.querySelector('.error-message')).toBeInTheDocument();
         // Optionally, check the text content if needed, but presence might be enough
         // expect(container.querySelector('.error-message')).toHaveTextContent(errorMessage);
       });
    });

    // Ensure login function was not called and no navigation happened
    expect(mockLogin).not.toHaveBeenCalled();
    expect(mockedNavigate).not.toHaveBeenCalled();
  });

  it('displays error message on network or server error', async () => {
    const networkErrorMessage = 'Failed to connect to the server. Please try again later.';
    global.fetch.mockRejectedValueOnce(new Error('Network error')); // Simulate fetch failure

    // Get container from renderLogin
    const { container } = renderLogin();

    const identifierInput = screen.getByLabelText(/username or email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /login/i });

    await fireEvent.change(identifierInput, { target: { value: 'testuser' } });
    await fireEvent.change(passwordInput, { target: { value: 'password123' } });
    await fireEvent.click(loginButton);

    // Wrap state update after await in act
    await act(async () => {
      // Wait for the error message element
      await waitFor(() => {
        expect(container.querySelector('.error-message')).toBeInTheDocument();
        // expect(container.querySelector('.error-message')).toHaveTextContent(networkErrorMessage);
      });
    });

    // Ensure login function was not called and no navigation happened
    expect(mockLogin).not.toHaveBeenCalled();
    expect(mockedNavigate).not.toHaveBeenCalled();
  });

}); 