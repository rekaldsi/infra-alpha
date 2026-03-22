const express = require('express');
const axios = require('axios');
const router = express.Router();

// GET /api/prices?symbols=VRT,ETN,SBGSY,ABB,CMI,NVT,ROK,CAT,ENS,HUBB,AMETEK
router.get('/', async (req, res) => {
  const symbols = req.query.symbols || 'VRT,ETN,SBGSY,ABB,CMI,NVT,ROK,CAT,ENS,HUBB,AMETEK';

  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/spark?symbols=${encodeURIComponent(symbols)}&range=1d&interval=5m`;
    const response = await axios.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
      },
      timeout: 8000,
    });

    const data = response.data;
    const result = {};

    if (data.spark?.result) {
      data.spark.result.forEach(item => {
        if (!item?.response?.[0]) return;
        const resp = item.response[0];
        const closes = resp.indicators?.quote?.[0]?.close || [];
        const validCloses = closes.filter(v => v != null);
        if (validCloses.length < 2) return;
        const price = validCloses[validCloses.length - 1];
        const open = validCloses[0];
        const change = price - open;
        const changePct = (change / open) * 100;
        result[item.symbol] = {
          price: parseFloat(price.toFixed(2)),
          change: parseFloat(change.toFixed(2)),
          changePct: parseFloat(changePct.toFixed(2)),
          history: validCloses.slice(-12).map(v => parseFloat(v.toFixed(2))),
        };
      });
    }

    if (Object.keys(result).length === 0) {
      return res.status(502).json({ error: 'price_fetch_failed', symbols: {} });
    }

    res.json(result);
  } catch (err) {
    console.error('Price fetch error:', err.message);
    res.status(502).json({ error: 'price_fetch_failed', symbols: {} });
  }
});

module.exports = router;
