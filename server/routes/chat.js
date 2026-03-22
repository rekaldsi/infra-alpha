const express = require('express');
const axios = require('axios');
const router = express.Router();

// POST /api/chat
// Body: { messages: [{role, content}], systemPrompt: string }
router.post('/', async (req, res) => {
  const { messages = [], systemPrompt = '' } = req.body;

  const ollamaUrl = process.env.OLLAMA_URL || 'http://localhost:11434';

  // 1. Try Ollama first
  try {
    const ollamaMessages = [
      { role: 'system', content: systemPrompt },
      ...messages,
    ];

    const response = await axios.post(`${ollamaUrl}/api/chat`, {
      model: 'qwen3:8b',
      stream: false,
      messages: ollamaMessages,
    }, {
      timeout: 30000,
    });

    const content = response.data?.message?.content || '';
    if (content) {
      return res.json({ content, model: 'qwen3:8b', source: 'ollama' });
    }
    throw new Error('Empty response from Ollama');
  } catch (ollamaErr) {
    console.warn('Ollama failed:', ollamaErr.message);
  }

  // 2. Fall back to Anthropic if API key is available
  const anthropicKey = process.env.ANTHROPIC_API_KEY;
  if (anthropicKey) {
    try {
      const response = await axios.post('https://api.anthropic.com/v1/messages', {
        model: 'claude-sonnet-4-6',
        max_tokens: 1024,
        system: systemPrompt,
        messages: messages,
      }, {
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': anthropicKey,
          'anthropic-version': '2023-06-01',
        },
        timeout: 30000,
      });

      const content = response.data?.content?.[0]?.text || '';
      return res.json({ content, model: 'claude-sonnet-4-6', source: 'anthropic' });
    } catch (anthropicErr) {
      console.error('Anthropic fallback failed:', anthropicErr.message);
    }
  }

  // 3. Both failed
  res.status(503).json({
    error: 'AI unavailable',
    content: 'Intelligence service temporarily unavailable.',
    source: 'error',
  });
});

module.exports = router;
