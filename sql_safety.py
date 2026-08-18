import sqlparse

FORBIDDEN_SQL_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "CREATE", "COPY", "CALL", "EXECUTE",
    "MERGE", "VACUUM", "REINDEX"]

DEFAULT_LIMIT = 1000

class SQLSafetyError(Exception):
    """Custom exception for SQL safety violations."""
    pass

def validate_sql(sql: str) -> str:
    """
    Validates the provided SQL query to ensure it does not contain any forbidden keywords.
    
    Args:
        sql (str): The SQL query to validate.
    
    Raises:
        SQLSafetyError: If the SQL query contains any forbidden keywords.
    """
    # Normalize the SQL query to uppercase for case-insensitive comparison
    normalized_sql = sqlparse.format(sql, keyword_case='upper')
    statements = sqlparse.parse(normalized_sql)
    # Check for forbidden keywords
    # Reject stacked queries — "SELECT 1; DROP TABLE users;" parses as TWO
    # statements even though only the first looks like what you asked for.
    
    if len(statements) > 1: 
        raise SQLSafetyError("Stacked queries are not allowed.")
    
    stmt= statements[0]
    
    if stmt.get_type() != 'SELECT':
        raise SQLSafetyError("Only SELECT statements are allowed.")
    
    # Defense in depth: scan every token, not just the statement-level type.
    # Guards against a forbidden keyword smuggled into a subquery, CTE, or
    # a place sqlparse's get_type() doesn't inspect.
    
    for token in stmt.flatten():
        if token.ttype in sqlparse.tokens.Keyword and token.value.upper() in FORBIDDEN_SQL_KEYWORDS:
            raise SQLSafetyError(f"Forbidden SQL keyword detected: {token.value}")

    result_sql = normalized_sql.strip()

    # No default LIMIT enforcement previously -- an unbounded broad question
    # against a huge table (posts: 59.5M rows, votes: 236M rows) could pull
    # an enormous result set into memory. Only add one if the statement
    # doesn't already have a top-level LIMIT; a harmless no-op for
    # aggregate queries (COUNT etc.) that return one row regardless.
    has_limit = any(
        token.ttype is sqlparse.tokens.Keyword and token.value.upper() == "LIMIT"
        for token in stmt.flatten()
    )
    if not has_limit:
        result_sql = result_sql.rstrip(";").rstrip() + f" LIMIT {DEFAULT_LIMIT};"

    return result_sql

if __name__ == "__main__":
    #sanity check the pass, fail, and default-LIMIT-injection paths

    good = 'SELECT * FROM posts WHERE posttypeid = 1 LIMIT 10;'
    bad = 'SELECT * FROM posts; DROP TABLE users;'
    unbounded = 'SELECT tags, COUNT(*) FROM posts GROUP BY tags;'

    print("Testing good SQL (already has LIMIT):")
    try:
        validated_sql = validate_sql(good)
        print(f"Passed: {validated_sql}")
    except SQLSafetyError as e:
        print(f"Failed: {e}")

    print("Testing bad SQL:")
    try:
        validated_sql = validate_sql(bad)
        print(f"Passed: {validated_sql}")
    except SQLSafetyError as e:
        print(f"Failed: {e}")

    print("Testing unbounded SQL (no LIMIT -- should get one injected):")
    try:
        validated_sql = validate_sql(unbounded)
        print(f"Passed: {validated_sql}")
    except SQLSafetyError as e:
        print(f"Failed: {e}")
