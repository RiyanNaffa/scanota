"""app/chat/sql_guard.py – SQL safety guard using sqlglot.

validate_sql(sql) -> str
    Returns a cleaned, safe SQL string.
    Raises UnsafeSQL on any policy violation.

Policy:
    - Exactly one statement
    - Root must be SELECT (CTEs allowed only with SELECT)
    - No DML/DDL/COPY/SET/CALL
    - Tables must be in ALLOWED_TABLES
    - Deny-list of dangerous functions
    - Strip comments
    - Append LIMIT 200 if absent; cap at 200
"""

from __future__ import annotations

import re

import sqlglot
import sqlglot.expressions as exp


class UnsafeSQL(Exception):
    pass


ALLOWED_TABLES = {"sales_flat", "products_public"}
MAX_LIMIT = 200
DEFAULT_LIMIT = 200

DENY_FUNCTIONS = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "lo_import",
    "lo_export",
    "lo_get",
    "lo_put",
    "dblink",
    "dblink_exec",
    "set_config",
    "current_setting",
    "pg_cancel_backend",
    "pg_terminate_backend",
    "copy_file_range",
    "pg_ls_dir",
}


def _strip_comments(sql: str) -> str:
    """Remove -- and /* */ comments."""
    # Remove block comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Remove line comments
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql.strip()


def validate_sql(sql: str) -> str:
    """Validate and sanitize SQL. Returns safe SQL or raises UnsafeSQL."""
    sql = _strip_comments(sql)
    if not sql:
        raise UnsafeSQL("Empty SQL")

    # Parse
    try:
        statements = sqlglot.parse(sql, dialect="postgres")
    except Exception as e:
        raise UnsafeSQL(f"SQL parse error: {e}") from e

    if len(statements) != 1:
        raise UnsafeSQL(f"Expected exactly 1 statement, got {len(statements)}")

    stmt = statements[0]
    if stmt is None:
        raise UnsafeSQL("Empty statement after parsing")

    # Root must be SELECT (or With which contains only SELECTs)
    if isinstance(stmt, exp.With):
        for cte in stmt.find_all(exp.CTE):
            inner = cte.find(exp.Select, exp.From)
            if inner is None:
                raise UnsafeSQL("CTE contains non-SELECT")
        # The body of the WITH must be SELECT
        body = stmt.this
        if not isinstance(body, exp.Select):
            raise UnsafeSQL("WITH body must be SELECT")
    elif not isinstance(stmt, exp.Select):
        kind = type(stmt).__name__
        raise UnsafeSQL(f"Only SELECT is allowed; got {kind}")

    # No DML/DDL inside (catches UPDATE/DELETE/INSERT/CREATE/DROP/TRUNCATE/ALTER)
    for bad_type in (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Command,
        exp.TruncateTable,
    ):
        if stmt.find(bad_type):
            raise UnsafeSQL(f"DML/DDL not allowed: {bad_type.__name__}")

    # Collect CTE names so we don't flag them as forbidden tables
    cte_names: set[str] = set()
    for cte in stmt.find_all(exp.CTE):
        if cte.alias:
            cte_names.add(cte.alias.lower())

    # Check all table references are in ALLOWED_TABLES (excluding CTE refs)
    for table in stmt.find_all(exp.Table):
        name = table.name.lower() if table.name else ""
        if name and name not in ALLOWED_TABLES and name not in cte_names:
            raise UnsafeSQL(f"Table '{name}' is not allowed. Allowed: {ALLOWED_TABLES}")

    # Check for denied functions
    for func in stmt.find_all(exp.Anonymous, exp.Func):
        func_name = ""
        if isinstance(func, exp.Anonymous):
            func_name = (func.name or "").lower()
        elif hasattr(func, "sql_name"):
            func_name = func.sql_name().lower()
        if func_name in DENY_FUNCTIONS or func_name.startswith("pg_"):
            raise UnsafeSQL(f"Function '{func_name}' is not allowed")

    # Serialize to SQL string
    clean_sql = stmt.sql(dialect="postgres").rstrip().rstrip(";")

    # Check and fix LIMIT using regex on the serialized string
    limit_match = re.search(r"\bLIMIT\s+(\d+)", clean_sql, flags=re.IGNORECASE)
    if limit_match is None:
        clean_sql = f"{clean_sql} LIMIT {DEFAULT_LIMIT}"
    else:
        try:
            limit_val = int(limit_match.group(1))
            if limit_val > MAX_LIMIT:
                clean_sql = re.sub(
                    r"\bLIMIT\s+\d+", f"LIMIT {MAX_LIMIT}", clean_sql, flags=re.IGNORECASE
                )
        except Exception:
            pass

    return clean_sql
