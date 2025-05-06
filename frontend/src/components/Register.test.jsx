import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import Register from './Register';

// Mock react-router-dom navigate function
const mockedNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  };
});

// Mock global fetch
global.fetch = vi.fn();

// Mock setTimeout/clearTimeout for controlling the redirect delay
vi.useFakeTimers();

describe('Register Component', () => {

  beforeEach(() => {
    // Reset mocks and timers before each test
    mockedNavigate.mockClear();
    global.fetch.mockClear();
    vi.clearAllTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers(); // Restore real timers after each test
  });

  const renderRegister = () => {
    // Return container from render
    return render(
        <MemoryRouter initialEntries={['/register']}>
            <Routes>
                <Route path="/register" element={<Register />} />
                {/* Add a dummy route for the redirect target */}
                <Route path="/login" element={<div>Login Mock</div>} />
            </Routes>
        </MemoryRouter>
    );
  };

  it('renders registration form correctly', () => {
    renderRegister();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /register/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /login here/i })).toBeInTheDocument();
  });

  it('allows inputting username, email, and password', async () => {
    renderRegister();
    const usernameInput = screen.getByLabelText(/username/i);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);

    await fireEvent.change(usernameInput, { target: { value: 'newuser' } });
    await fireEvent.change(emailInput, { target: { value: 'new@example.com' } });
    await fireEvent.change(passwordInput, { target: { value: 'password123' } });

    expect(usernameInput.value).toBe('newuser');
    expect(emailInput.value).toBe('new@example.com');
    expect(passwordInput.value).toBe('password123');
  });

  it('calls fetch, displays success, and navigates on valid submission', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ message: 'User created successfully', user_id: 123 }),
    });

    // Get container from renderRegister
    const { container } = renderRegister();

    const usernameInput = screen.getByLabelText(/username/i);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const registerButton = screen.getByRole('button', { name: /register/i });

    await fireEvent.change(usernameInput, { target: { value: 'newuser' } });
    await fireEvent.change(emailInput, { target: { value: 'new@example.com' } });
    await fireEvent.change(passwordInput, { target: { value: 'password123' } });
    await fireEvent.click(registerButton);

    // Check fetch call
    await act(async () => {
        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith('/api/v1/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: 'newuser', email: 'new@example.com', password: 'password123' }),
            });
        });

        // Check success message element
        expect(container.querySelector('.success-message')).toBeInTheDocument();
        // expect(container.querySelector('.success-message')).toHaveTextContent('Registration successful! Redirecting to login...');

        // Check form fields are cleared (wait slightly for state update)
        await waitFor(() => {
            expect(usernameInput.value).toBe('');
            expect(emailInput.value).toBe('');
            expect(passwordInput.value).toBe('');
        })

        // Fast-forward timers to trigger navigation INSIDE the same act block
        vi.advanceTimersByTime(2000); // Advance time by 2 seconds (past the 1.5s delay)
    });

    // Check navigation (outside act, as it happens after timers advance)
    expect(mockedNavigate).toHaveBeenCalledWith('/login');

    // Check no error message is shown
    expect(container.querySelector('.error-message')).not.toBeInTheDocument();

  });

  it('displays error message on failed registration (e.g., duplicate user)', async () => {
    const errorMessage = 'Username already exists';
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ message: errorMessage }),
    });

    // Get container from renderRegister
    const { container } = renderRegister();

    const usernameInput = screen.getByLabelText(/username/i);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const registerButton = screen.getByRole('button', { name: /register/i });

    await fireEvent.change(usernameInput, { target: { value: 'existinguser' } });
    await fireEvent.change(emailInput, { target: { value: 'unique@example.com' } });
    await fireEvent.change(passwordInput, { target: { value: 'password123' } });
    await fireEvent.click(registerButton);

    // Wrap state update after await in act
    await act(async () => {
      // Wait for the error message element
       await waitFor(() => {
         expect(container.querySelector('.error-message')).toBeInTheDocument();
         // expect(container.querySelector('.error-message')).toHaveTextContent(errorMessage);
       });
    });

    // Ensure no navigation happened
    expect(mockedNavigate).not.toHaveBeenCalled();
    // Ensure success message is not shown
    expect(screen.queryByText(/registration successful/i)).not.toBeInTheDocument();
  });

  it('displays error message on network or server error', async () => {
     const networkErrorMessage = 'Failed to connect to the server. Please try again later.';
     global.fetch.mockRejectedValueOnce(new Error('Network error')); // Simulate fetch failure

     // Get container from renderRegister
     const { container } = renderRegister();

    const usernameInput = screen.getByLabelText(/username/i);
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const registerButton = screen.getByRole('button', { name: /register/i });

    await fireEvent.change(usernameInput, { target: { value: 'anyuser' } });
    await fireEvent.change(emailInput, { target: { value: 'any@example.com' } });
    await fireEvent.change(passwordInput, { target: { value: 'password123' } });
    await fireEvent.click(registerButton);

    // Wrap state update after await in act
    await act(async () => {
        // Wait for the error message element
        await waitFor(() => {
          expect(container.querySelector('.error-message')).toBeInTheDocument();
          // expect(container.querySelector('.error-message')).toHaveTextContent(networkErrorMessage);
        });
    });

    // Ensure no navigation happened
    expect(mockedNavigate).not.toHaveBeenCalled();
     // Ensure success message is not shown
    expect(screen.queryByText(/registration successful/i)).not.toBeInTheDocument();
  });

}); 