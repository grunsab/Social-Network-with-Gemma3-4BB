import React from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  Navigate,
  NavLink
} from 'react-router-dom';

import { useAuth } from './context/AuthContext'; // Import useAuth
import Login from './components/Login';
import Register from './components/Register';
import Dashboard from './components/Dashboard'; // Import Dashboard
import ProtectedRoute from './components/ProtectedRoute'; // Import ProtectedRoute
import Profile from './components/Profile'; // Import Profile component
import CategoryView from './components/CategoryView'; // Import CategoryView
import ManageInvites from './components/ManageInvites'; // Import ManageInvites
import FriendRequests from './components/FriendRequests'; // Import FriendRequests
import PopularAmpersoundsPage from './components/PopularAmpersoundsPage'; // Import new page
import './App.css';
import Spinner from './components/Spinner'; // Import Spinner

function App() {
  const { currentUser, loading, logout } = useAuth(); // Get user and logout

  // Handle logout directly in nav for simplicity here
  const handleLogout = async () => {
    await logout();
    // No need to navigate here, ProtectedRoute will handle redirect if on protected page
  };

  if (loading) {
      // Use contained spinner for initial app load
      return <Spinner contained={true} />; 
  }

  return (
    <Router>
      <nav>
        <ul>
          {/* Add App Title/Link */} 
          <li> 
            <Link to="/" className="nav-title">SocialNet</Link>
          </li>
          <li> {/* Public link to Popular Ampersounds */}
            <NavLink to="/popular-ampersounds" className={({ isActive }) => isActive ? "active" : ""}>Popular Sounds</NavLink>
          </li>

          {currentUser ? (
            <>
              <li>
                <NavLink to="/" className={({ isActive }) => isActive ? "active" : ""} end>Dashboard</NavLink>
              </li>
              <li>
                <NavLink 
                    to={`/profile/${currentUser.username}`}
                    className={({ isActive }) => isActive ? "active" : ""}
                >
                    My Profile
                </NavLink>
              </li>
              <li>
                <NavLink to="/manage-invites" className={({ isActive }) => isActive ? "active" : ""}>Manage Invites</NavLink>
              </li>
              <li>
                <NavLink to="/friend-requests" className={({ isActive }) => isActive ? "active" : ""}>Friend Requests</NavLink>
              </li>
              <li>
                <button onClick={handleLogout} className="logout-button">
                  Logout ({currentUser.username})
                </button>
              </li>
            </>
          ) : (
            <>
              <li>
                <NavLink to="/login" className={({ isActive }) => isActive ? "active" : ""}>Login</NavLink>
              </li>
              <li>
                <NavLink to="/register" className={({ isActive }) => isActive ? "active" : ""}>Register</NavLink>
              </li>
            </>
          )}
        </ul>
      </nav>

      <main className="main-content">
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={!currentUser ? <Login /> : <Navigate replace to="/" />} />
          <Route path="/register" element={!currentUser ? <Register /> : <Navigate replace to="/" />} />
          <Route path="/popular-ampersounds" element={<PopularAmpersoundsPage />} /> {/* New public route */}

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
             <Route path="/" element={<Dashboard />} />
             <Route path="/profile/:username" element={<Profile />} />
             <Route path="/category/:categoryName" element={<CategoryView />} />
             <Route path="/manage-invites" element={<ManageInvites />} />
             <Route path="/friend-requests" element={<FriendRequests />} />
          </Route>
          
           {/* Optional: Catch-all route for 404 */}
          {/* <Route path="*" element={<NotFound />} /> */}
        </Routes>
      </main>
    </Router>
  );
}

export default App;
