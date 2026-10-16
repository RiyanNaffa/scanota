#!/usr/bin/env bash
# app/db/init/02-roles.sh
# Creates scanota_ro (read-only) role and grants SELECT on views only.
# Runs once at Postgres container first start via /docker-entrypoint-initdb.d/.
# Idempotent: uses DO $$ ... $$ to create role only if it does not exist.
set -euo pipefail

: "${POSTGRES_RO_PASSWORD:?POSTGRES_RO_PASSWORD must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${POSTGRES_USER:?POSTGRES_USER must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL

    -- Create read-only role if it does not exist
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'scanota_ro') THEN
            CREATE ROLE scanota_ro LOGIN PASSWORD '${POSTGRES_RO_PASSWORD}';
        ELSE
            ALTER ROLE scanota_ro WITH PASSWORD '${POSTGRES_RO_PASSWORD}';
        END IF;
    END
    \$\$;

    -- Restrict default transaction mode and query time
    ALTER ROLE scanota_ro SET default_transaction_read_only = on;
    ALTER ROLE scanota_ro SET statement_timeout = '5s';

    -- Revoke all defaults (schema public grants)
    REVOKE ALL ON ALL TABLES IN SCHEMA public FROM scanota_ro;
    REVOKE ALL ON SCHEMA public FROM scanota_ro;

    -- Grant connect and usage
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO scanota_ro;
    GRANT USAGE ON SCHEMA public TO scanota_ro;

    -- Grant SELECT on the two views only
    GRANT SELECT ON sales_flat      TO scanota_ro;
    GRANT SELECT ON products_public TO scanota_ro;

EOSQL

echo "02-roles.sh: scanota_ro role configured successfully."
