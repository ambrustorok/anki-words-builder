import React, { useEffect, useState } from 'react';
import AuthService from '../services/auth.service';
import UserService from '../services/user.service';

const Dashboard = () => {
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const response = await UserService.getUser();
        setUser(response.data);
      } catch (error) {
        setError('Failed to fetch user data.');
      }
    };

    fetchUser();
  }, []);

  const handleLogout = () => {
    AuthService.logout();
    window.location.reload();
  };

  if (error) {
    return <div>{error}</div>;
  }

  return (
    <div>
      {user ? (
        <div>
          <h1>Welcome, {user.username}!</h1>
            <iframe
                src="http://localhost:8000/gradio" // Replace with your FastAPI app's URL
                width="100%"
                height="600px"
                style={{ border: 'none' }}
                title="Gradio App"
            ></iframe>
          <button onClick={handleLogout}>Logout</button>
        </div>
      ) : (
        <p>Loading user data...</p>
      )}
    </div>
  );
};

export default Dashboard;
