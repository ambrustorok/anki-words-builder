// src/services/user.service.js

import axios from 'axios';
import AuthService from './auth.service';

const API_URL = 'http://localhost:8000'; // Adjust based on your backend URL

const getUser = () => {
  const user = AuthService.getCurrentUser();

  if (user && user.access_token) {
    return axios.get(`${API_URL}/users/me`, {
      headers: {
        Authorization: `Bearer ${user.access_token}`,
      },
    });
  } else {
    return Promise.reject('No user token found');
  }
};

// Exporting as a named object
const UserService = {
  getUser,
};

export default UserService;
