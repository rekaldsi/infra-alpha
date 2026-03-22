require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');

const pricesRouter = require('./routes/prices');
const chatRouter = require('./routes/chat');

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// Static files from client/
app.use(express.static(path.join(__dirname, '../client')));

// Routes
app.use('/api/prices', pricesRouter);
app.use('/api/chat', chatRouter);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', model: 'qwen3:8b', ts: new Date().toISOString() });
});

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../client/index.html'));
});

app.listen(PORT, () => {
  console.log(`Infra Alpha server running on port ${PORT}`);
  console.log(`Health: http://localhost:${PORT}/health`);
  console.log(`Model: qwen3:8b (Ollama), fallback: Anthropic claude-sonnet-4-6`);
});
