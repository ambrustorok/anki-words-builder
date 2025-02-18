import axios from 'axios';

const API_URL = 'http://localhost:8000'; // Adjust based on your backend URL

const register = (username, password) => {
  return axios.post(`${API_URL}/register`, { username, password });
};

const login = (username, password) => {
  return axios
    .post(
      `${API_URL}/token`,
      new URLSearchParams({ username, password }),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      }
    )
    .then((response) => {
      if (response.data.access_token) {
        localStorage.setItem('user', JSON.stringify(response.data));
      }
      return response.data;
    });
};

const logout = () => {
  localStorage.removeItem('user');
};

const getCurrentUser = () => {
  return JSON.parse(localStorage.getItem('user'));
};

// Assigning the object to a variable before exporting
const AuthService = {
  register,
  login,
  logout,
  getCurrentUser,
};

export default AuthService;
