import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css';

const Dashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const redirectToChat = () => {
    // Redirect to Chainlit app (now mounted at /chat)
    window.location.href = 'http://localhost:8000/chat';
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Welcome, {user?.name}</h1>
        <button onClick={handleLogout} className="logout-btn">
          Logout
        </button>
      </header>

      <div className="dashboard-content">
        <div className="user-info-card">
          <img 
            src={user?.image}
            alt="Profile" 
            className="profile-picture"
            onError={(e) => {
              e.target.src = 'https://via.placeholder.com/80x80/cccccc/666666?text=User';
            }}
            referrerPolicy="no-referrer"
          />
          <h2>{user?.name}</h2>
          <p>{user?.email}</p>
        </div>

        <div className="actions-card">
          <h3>Quick Actions</h3>
          <button onClick={redirectToChat} className="chat-btn">
            Start AI Chat
          </button>
          <button className="settings-btn">
            Account Settings
          </button>
        </div>

        <div className="subscription-card">
          <h3>Subscription Status</h3>
          <p className="status">Free Tier</p>
          <p className="description">Upgrade to unlock premium features</p>
          <button className="upgrade-btn">
            Upgrade to Premium
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;