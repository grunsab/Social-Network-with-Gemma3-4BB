import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Spinner from './Spinner'; // Assumed import
import { FaUserAlt, FaEnvelope, FaLock } from 'react-icons/fa'; // Import icons
import './AuthForms.css'; // Shared CSS for Login/Register

function Register() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const response = await fetch('/api/v1/register', { // Assuming backend runs on the same origin or proxy is set up
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          username: username, 
          email: email,
          password: password 
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        // Handle errors (e.g., 400, 409, 500)
        setError(data.message || 'An error occurred during registration.');
      } else {
        // Registration successful
        console.log('Registration successful:', data);
        setSuccess('Registration successful! Redirecting to login...');
        // Clear form
        setUsername('');
        setEmail('');
        setPassword('');
        // Redirect to the login page after a short delay
        setTimeout(() => {
           navigate('/login');
        }, 1500); // 1.5 second delay
      }
    } catch (err) {
      console.error('Registration API call failed:', err);
      setError('Failed to connect to the server. Please try again later.');
    } finally {
      // Don't reset loading immediately if we are delaying navigation
      if (!success) { // Only set loading false if not in success-redirect state
         setLoading(false);
      } 
      // Or simply: setLoading(false); if instant redirect is preferred
    }
  };

  return (
    <div className="card" style={{ maxWidth: '400px', margin: '2rem auto' }}>
      <h2>Register</h2>
      {error && <p className="error-message">{error}</p>}
      {success && <p className="success-message">{success}</p>}
      <form onSubmit={handleSubmit}>
        <div className="input-group"> 
          <label htmlFor="username">Username:</label>
          <FaUserAlt className="input-icon" />
          <input 
            type="text"
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className="input-with-icon"
          />
        </div>
        <div className="input-group">
          <label htmlFor="email">Email:</label>
          <FaEnvelope className="input-icon" />
          <input 
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="input-with-icon"
          />
        </div>
        <div className="input-group">
          <label htmlFor="password">Password:</label>
          <FaLock className="input-icon" />
          <input 
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="input-with-icon"
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? <Spinner inline={true} /> : 'Register'}
        </button>
      </form>
      <p>
        Already have an account? <Link to="/login">Login here</Link>
      </p>
    </div>
  );
}

export default Register; 