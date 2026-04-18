CREATE TABLE IF NOT EXISTS infra_trader_accounts (
  user_name        TEXT PRIMARY KEY,
  display_name     TEXT NOT NULL,
  alpaca_key_id    TEXT,
  alpaca_secret    TEXT,
  mode             TEXT DEFAULT 'paper',
  enabled          BOOLEAN DEFAULT FALSE,
  risk_pct         FLOAT DEFAULT 2.0,
  max_position     INT DEFAULT 100,
  telegram_chat_id TEXT,
  connected        BOOLEAN DEFAULT FALSE,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default accounts if not exists
INSERT INTO infra_trader_accounts (user_name, display_name, telegram_chat_id)
VALUES
  ('jerry', 'Jerry', '7638568632'),
  ('frank', 'Frank', NULL)
ON CONFLICT (user_name) DO NOTHING;
