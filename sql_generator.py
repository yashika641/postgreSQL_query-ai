import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from schema import get_schema
from schema_prompt import render_schema_ddl

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SYSTEM_PROMPT = """
You are a PostgreSQL expert generating read-only queries against a Stack
Overflow database.

Rules:
- Output ONLY a single valid PostgreSQL SELECT statement. No markdown
  fences, no explanation, no comments.
- Never generate INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE - SELECT only.
- Use only the tables, columns, and lookup-code values given in the schema.
- FK relationships shown as comments are NOT enforced by the database
  (orphaned references exist) - prefer LEFT JOIN over INNER JOIN where a
  match isn't guaranteed.
""".strip()


def generate_sql(question: str, previous_error: str | None = None) -> str:
    schema_text = render_schema_ddl(get_schema())
    user_message = f"Schema:\n{schema_text}\n\nQuestion: {question}\n\nSQL:"

    if previous_error:
        user_message += (
            f"\n\nYour previous attempt failed with this error:\n{previous_error}\n"
            "Fix the query and try again."
        )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    sql = response.text.strip()
    if sql.startswith("```"):
        sql = sql.strip("`").removeprefix("sql").strip()
    return sql


if __name__ == "__main__":
    test_question = "How many questions were posted in 2023?"
    sql = generate_sql(test_question)
    print(sql)
