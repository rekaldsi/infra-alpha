-- InfraAlpha: infra_trades table
-- Run this once in Supabase SQL editor

CREATE TABLE IF NOT EXISTS infra_trades (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_name       TEXT NOT NULL,
  symbol          TEXT NOT NULL,
  side            TEXT NOT NULL,
  shares          INT NOT NULL,
  entry_price     FLOAT,
  exit_price      FLOAT,
  stop_price      FLOAT,
  score           FLOAT,
  conviction      TEXT,
  pattern         TEXT,
  news_score      FLOAT,
  macro_regime    TEXT,
  order_id        TEXT,
  status          TEXT DEFAULT 'open',
  pnl             FLOAT,
  pnl_after_fees  FLOAT,
  slippage_est    FLOAT,
  opened_at       TIMESTAMPTZ DEFAULT NOW(),
  closed_at       TIMESTAMPTZ,
  notes           TEXT
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS infra_trades_user_idx ON infra_trades(user_name);
CREATE INDEX IF NOT EXISTS infra_trades_symbol_idx ON infra_trades(symbol);
CREATE INDEX IF NOT EXISTS infra_trades_opened_at_idx ON infra_trades(opened_at DESC);
CREATE INDEX IF NOT EXISTS infra_trades_conviction_idx ON infra_trades(conviction);
