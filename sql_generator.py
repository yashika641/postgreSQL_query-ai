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
- When counting rows, use COUNT(id) or COUNT(1), never COUNT(*). posts
  (~59.5M rows) and votes (~236M rows) are large enough that COUNT(*)
  risks hitting the query's statement timeout.
""".strip()

class SQLGenerationError(Exception):
    '''raised when gemini's response isnt usable sql at all
    -- (empty response , safety- filtered, or effectively refusal)'''

def generate_sql(question: str, previous_error: str | None = None, history: list | None = None) -> str:
    schema_text = render_schema_ddl(get_schema())
    conversation_context = ""
    if history:
        conversation_context = "conversation so far :\n"
        for turn in history:
            conversation_context += (
                f"q: {turn['question']}\n"
                f"SQL:{turn['sql']}\n"
                f"(returned {turn['row_count']} rows)\n \n"
            )
    user_message = f"Schema:\n{schema_text}\n\n{conversation_context}Question: {question}\n\nSQL:"

    if previous_error:
        user_message += (
            f"\n\nYour previous attempt failed with this error:\n{previous_error}\n"
            "Fix the query and try again."
        )

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )
    if response.text is None:
        raise SQLGenerationError('Gemini returned no text (possibly blocked by safety filters)')

    sql = response.text.strip()
    if sql.startswith("```"):
        sql = sql.strip("`").removeprefix("sql").strip()
        
    if not sql:
        raise SQLGenerationError ('gemini returned a empty response after cleanup')
    return sql




if __name__ == "__main__":
    test_question = "How many questions were posted in 2023?"
    sql = generate_sql(test_question)
    print(sql)
