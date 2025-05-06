import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Spinner from './Spinner'; // Assumed import
import { FaUserAlt, FaLock } from 'react-icons/fa'; // Import icons
import './AuthForms.css'; // Shared CSS for Login/Register

function Login() {
  const [identifier, setIdentifier] = useState(''); // Can be username or email
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('/api/v1/login', { // Assuming backend runs on the same origin or proxy is set up
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          identifier: identifier, 
          password: password 
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        // Handle errors (e.g., 400, 401, 500)
        setError(data.message || 'An error occurred during login.');
      } else {
        // Login successful
        console.log('Login successful:', data.user);
        login(data.user);
        navigate('/');
      }
    } catch (err) {
      console.error('Login API call failed:', err);
      setError('Failed to connect to the server. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: '400px', margin: '2rem auto' }}>
      <h2>Login</h2>
      {error && <p className="error-message">{error}</p>}
      <form onSubmit={handleSubmit}>
        {/* Input Group for Username/Email */}
        <div className="input-group"> 
          <label htmlFor="identifier">Username or Email:</label>
          <FaUserAlt className="input-icon" /> {/* Icon */} 
          <input 
            type="text"
            id="identifier"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            required
            className="input-with-icon" // Class for padding
          />
        </div>
        {/* Input Group for Password */}
        <div className="input-group"> 
          <label htmlFor="password">Password:</label>
          <FaLock className="input-icon" /> {/* Icon */} 
          <input 
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="input-with-icon" // Class for padding
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? <Spinner inline={true} /> : 'Login'}
        </button>
      </form>
      <p>
        Don't have an account? <Link to="/register">Register here</Link>
      </p>
    </div>
  );
}

export default Login; 