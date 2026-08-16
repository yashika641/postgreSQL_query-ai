import pandas as pd
from database import engine
from sql_generator import generate_sql
from sql_safety import validate_sql, SQLSafetyError
from pandas.errors import DatabaseError

max_attempts = 3

def run_question(question: str) -> pd.DataFrame:
    """
    Generates a SQL query based on the provided question, validates it, and executes it against the database.

    Args:
        question (str): The natural language question to be converted into a SQL query.

    Returns:
        pd.DataFrame: The result of the executed SQL query.
    """
    previous_error = None

    for _ in range(1, max_attempts + 1):
        # Generate the SQL query, feeding back the last failure so the
        # model can actually fix it instead of repeating the same mistake.
        sql = generate_sql(question, previous_error=previous_error)

        try:
            # Validate the SQL query
            validated_sql = validate_sql(sql)
        except SQLSafetyError as e:
            previous_error = f"generated SQL failed safety validation: {e}"
            continue  # Try again with a new SQL generation

        try:
            with engine.connect() as conn:
                return pd.read_sql(validated_sql, conn)
        except DatabaseError as e:
            previous_error = f"database execution error: {e}"
            continue  # Try again with a new SQL generation

    raise RuntimeError(f"Failed to execute the question after {max_attempts} attempts. Last error: {previous_error}")


if __name__ == "__main__":
    test_question = "How many questions were posted in 2023?"
    try:
        result_df = run_question(test_question)
        print(result_df)
    except RuntimeError as e:
        print(f"Error: {e}")