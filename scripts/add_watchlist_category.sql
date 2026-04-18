ALTER TABLE infra_watchlist ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'general';
ALTER TABLE infra_watchlist ADD COLUMN IF NOT EXISTS added_by_user TEXT DEFAULT 'frank';
COMMENT ON COLUMN infra_watchlist.category IS 'Sector category: defense, data-center, frank-portfolio, general, jerry-picks, indexes';
