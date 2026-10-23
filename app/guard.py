"""
Safety checks for SQL written by the LLM, before it touches the database.

Three layers:
  1. this parser check: exactly one read-only SELECT on known tables, no PRAGMA/ATTACH/etc.
  2. a row cap: results are wrapped in LIMIT MAX_ROWS
  3. the database itself is opened read-only with a time limit (see engine.run_sql)
"""
import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"delivered_orders", "orders", "order_items", "payments", "reviews",
                  "customers", "sellers", "products", "category_en"}
MAX_ROWS = 500
BLOCKED = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command,
           exp.Pragma, exp.Attach, exp.Detach, exp.Transaction, exp.Commit, exp.Rollback)
BLOCKED_FUNCS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


class UnsafeSQL(ValueError):
    """Raised when a query is not a single read-only SELECT.
    repairable=True for honest mistakes (typo in a table name, bad syntax) the LLM may fix."""

    def __init__(self, reason, repairable=False):
        super().__init__(reason)
        self.repairable = repairable


def check_sql(sql: str) -> str:
    """Return a safe, row-capped version of `sql`, or raise UnsafeSQL with the reason."""
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise UnsafeSQL("empty query")
    try:
        trees = [t for t in sqlglot.parse(sql, read="sqlite") if t is not None]
    except sqlglot.errors.ParseError as e:
        raise UnsafeSQL(f"could not parse the SQL: {str(e).splitlines()[0]}", repairable=True) from None
    if len(trees) != 1:
        raise UnsafeSQL("only one statement is allowed")
    tree = trees[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise UnsafeSQL("only SELECT queries are allowed")
    for node in tree.walk():
        if isinstance(node, BLOCKED):
            raise UnsafeSQL(f"{type(node).__name__.upper()} is not allowed")
        if isinstance(node, exp.Anonymous) and node.name.lower() in BLOCKED_FUNCS:
            raise UnsafeSQL(f"function {node.name} is not allowed")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if t.args.get("db") or t.args.get("catalog"):
            raise UnsafeSQL("schema-qualified table names are not allowed")
        if name not in ALLOWED_TABLES and name not in ctes:
            raise UnsafeSQL(f"unknown table: {t.name}", repairable=True)
    limit = tree.args.get("limit")
    if isinstance(tree, exp.Select) and limit is None:
        return f"{sql}\nLIMIT {MAX_ROWS}"
    n = limit.expression if limit is not None else None
    if isinstance(n, exp.Literal) and n.is_int and int(n.name) <= MAX_ROWS:
        return sql
    return f"SELECT * FROM ({sql}) LIMIT {MAX_ROWS}"
