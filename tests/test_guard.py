"""The safety check must let normal questions through and stop everything else."""
import pytest

from app.guard import MAX_ROWS, UnsafeSQL, check_sql

SAFE = [
    "SELECT COUNT(*) FROM orders",
    "SELECT customer_state, ROUND(100.0*AVG(is_late),2) FROM delivered_orders GROUP BY 1 ORDER BY 2 DESC LIMIT 5",
    "WITH t AS (SELECT * FROM orders) SELECT COUNT(*) FROM t;",
    "SELECT strftime('%Y', order_purchase_timestamp) AS y, COUNT(*) FROM orders GROUP BY y",
]
UNSAFE = [
    "DROP TABLE orders", "DELETE FROM orders", "UPDATE orders SET order_status = 'x'",
    "INSERT INTO orders VALUES (1)", "CREATE TABLE x (a)", "VACUUM",
    "PRAGMA table_info(orders)", "ATTACH DATABASE 'x.db' AS x",
    "SELECT 1; DROP TABLE orders",                       # two statements
    "SELECT * FROM sqlite_master",                        # system table
    "SELECT * FROM main.orders",                          # schema-qualified
    "SELECT load_extension('x')", "SELECT readfile('/etc/passwd')",
    "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x",
    "", "  ;  ",
]


@pytest.mark.parametrize("sql", SAFE)
def test_safe_queries_pass(sql):
    assert check_sql(sql)


@pytest.mark.parametrize("sql", UNSAFE)
def test_unsafe_queries_blocked(sql):
    with pytest.raises(UnsafeSQL):
        check_sql(sql)


def test_row_cap_added_when_missing():
    assert check_sql("SELECT * FROM orders").endswith(f"LIMIT {MAX_ROWS}")


def test_big_limit_is_capped():
    assert check_sql("SELECT * FROM orders LIMIT 100000").endswith(f") LIMIT {MAX_ROWS}")


def test_small_limit_kept():
    assert check_sql("SELECT * FROM orders LIMIT 5") == "SELECT * FROM orders LIMIT 5"
