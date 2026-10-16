-- scanota database schema
-- Apply via: psql -U scanota -d scanota -f schema.sql
-- Idempotent: safe to run on a fresh database only (uses CREATE TABLE, not CREATE TABLE IF NOT EXISTS,
-- because it is mounted as a Docker init file and runs exactly once on first start).

-- ============================================================
-- Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS products (
    sku_id            TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    category          TEXT NOT NULL,
    unit              TEXT NOT NULL,
    cost_price        NUMERIC(14,0),
    current_stock     NUMERIC(14,2) NOT NULL DEFAULT 0,
    lead_time_days    INTEGER NOT NULL DEFAULT 3 CHECK (lead_time_days >= 0),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS product_aliases (
    id                BIGSERIAL PRIMARY KEY,
    alias_norm        TEXT NOT NULL UNIQUE,
    alias_raw         TEXT NOT NULL,
    sku_id            TEXT NOT NULL REFERENCES products(sku_id) ON DELETE CASCADE,
    source            TEXT NOT NULL CHECK (source IN ('seed', 'user_correction')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    id                BIGSERIAL PRIMARY KEY,
    tx_date           DATE NOT NULL,
    channel           TEXT NOT NULL CHECK (channel IN ('online', 'offline')),
    customer          TEXT,
    total             NUMERIC(14,0) NOT NULL CHECK (total >= 0),
    source            TEXT NOT NULL CHECK (source IN ('scan', 'webhook', 'csv', 'seed')),
    status            TEXT NOT NULL CHECK (status IN ('confirmed', 'needs_review')),
    confidence        REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    issues            JSONB NOT NULL DEFAULT '[]'::jsonb,
    external_ref      TEXT UNIQUE,
    receipt_image_path TEXT,
    raw_extraction    JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS transaction_items (
    id                BIGSERIAL PRIMARY KEY,
    transaction_id    BIGINT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    item_name_raw     TEXT NOT NULL,
    sku_id            TEXT REFERENCES products(sku_id),
    qty               NUMERIC(14,2) NOT NULL CHECK (qty > 0),
    unit              TEXT,
    unit_price        NUMERIC(14,0) NOT NULL CHECK (unit_price >= 0),
    line_total        NUMERIC(14,0) NOT NULL CHECK (line_total >= 0),
    match_score       REAL
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_transactions_tx_date  ON transactions(tx_date);
CREATE INDEX IF NOT EXISTS idx_transactions_status   ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_tx_items_tx_id        ON transaction_items(transaction_id);
CREATE INDEX IF NOT EXISTS idx_tx_items_sku_id       ON transaction_items(sku_id);

-- ============================================================
-- Views (for the read-only role)
-- ============================================================

CREATE OR REPLACE VIEW sales_flat AS
SELECT
    t.id           AS transaction_id,
    t.tx_date,
    t.channel,
    t.customer,
    i.sku_id,
    p.name         AS product_name,
    p.category,
    i.qty,
    COALESCE(i.unit, p.unit) AS unit,
    i.unit_price,
    i.line_total
FROM transactions t
JOIN transaction_items i ON i.transaction_id = t.id
LEFT JOIN products p     ON p.sku_id = i.sku_id
WHERE t.status = 'confirmed';

CREATE OR REPLACE VIEW products_public AS
SELECT
    sku_id,
    name,
    category,
    unit,
    current_stock,
    lead_time_days
FROM products;
