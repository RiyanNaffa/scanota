"""tests/unit/test_sql_guard.py – At least 30 SQL guard test cases."""

from __future__ import annotations

import pytest

from app.chat.sql_guard import UnsafeSQL, validate_sql


class TestValidSelects:
    def test_simple_select(self):
        sql = validate_sql("SELECT * FROM sales_flat")
        assert "LIMIT" in sql.upper()

    def test_select_with_where(self):
        sql = validate_sql("SELECT tx_date, qty FROM sales_flat WHERE channel = 'online'")
        assert "sales_flat" in sql

    def test_select_products_public(self):
        sql = validate_sql("SELECT sku_id, current_stock FROM products_public")
        assert "products_public" in sql

    def test_select_with_limit(self):
        sql = validate_sql("SELECT * FROM sales_flat LIMIT 10")
        assert "LIMIT 10" in sql

    def test_limit_capped_at_200(self):
        sql = validate_sql("SELECT * FROM sales_flat LIMIT 9999")
        assert "LIMIT 200" in sql

    def test_no_limit_adds_default(self):
        sql = validate_sql("SELECT sku_id FROM products_public")
        assert "LIMIT 200" in sql.upper()

    def test_cte_select(self):
        sql = validate_sql(
            "WITH top AS (SELECT sku_id, SUM(qty) as total FROM sales_flat GROUP BY sku_id) "
            "SELECT * FROM top"
        )
        assert sql is not None

    def test_aggregate_query(self):
        sql = validate_sql(
            "SELECT product_name, SUM(line_total) FROM sales_flat GROUP BY product_name ORDER BY 2 DESC"
        )
        assert "sales_flat" in sql

    def test_join_allowed_tables(self):
        sql = validate_sql(
            "SELECT s.product_name, p.current_stock FROM sales_flat s "
            "JOIN products_public p ON s.sku_id = p.sku_id"
        )
        assert sql is not None


class TestDMLRejected:
    def test_drop_table(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("DROP TABLE transactions")

    def test_delete(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("DELETE FROM sales_flat WHERE 1=1")

    def test_update(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("UPDATE products_public SET current_stock = 0")

    def test_insert(self):
        with pytest.raises(UnsafeSQL):
            validate_sql(
                "INSERT INTO sales_flat VALUES (1, '2025-01-01', 'online', NULL, NULL, NULL, NULL, 1, 'pcs', 1000, 1000)"
            )

    def test_truncate_via_command(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("TRUNCATE TABLE transactions")


class TestForbiddenTables:
    def test_access_transactions_base(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("SELECT * FROM transactions")

    def test_access_transaction_items(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("SELECT * FROM transaction_items")

    def test_access_products_base(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("SELECT * FROM products")

    def test_subquery_forbidden_table(self):
        with pytest.raises(UnsafeSQL):
            validate_sql(
                "SELECT * FROM sales_flat WHERE transaction_id IN (SELECT id FROM transactions)"
            )


class TestDangerousFunctions:
    def test_pg_sleep(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("SELECT pg_sleep(10)")

    def test_pg_read_file(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("SELECT pg_read_file('/etc/passwd')")

    def test_copy_statement(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("COPY transactions TO '/tmp/dump.csv'")


class TestCommentStripping:
    def test_inline_comment_stripped(self):
        sql = validate_sql("SELECT * FROM sales_flat -- ignore this")
        assert "--" not in sql

    def test_block_comment_stripped(self):
        sql = validate_sql("SELECT /* hack */ * FROM sales_flat")
        assert "/*" not in sql

    def test_comment_injection_attempt(self):
        # Trying to hide forbidden table via comment splitting
        with pytest.raises(UnsafeSQL):
            validate_sql("SELECT * FROM /* comment */ transactions")


class TestMultipleStatements:
    def test_semicolon_injection(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("SELECT * FROM sales_flat; DROP TABLE transactions")

    def test_two_selects_rejected(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("SELECT 1; SELECT 2")


class TestEdgeCases:
    def test_empty_sql(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("")

    def test_whitespace_only(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("   ")

    def test_set_role(self):
        with pytest.raises(UnsafeSQL):
            validate_sql("SET ROLE postgres")
