require('dotenv').config();
const express = require('express');
const authRoutes = require('./routes/auth');

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(express.json());
app.use('/api/auth', authRoutes);

// Start the server
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
