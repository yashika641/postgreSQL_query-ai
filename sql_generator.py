import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

from schema import get_schema
from schema_prompt import render_schema_ddl
MAX_VERBATIM_TURNS = 5
load_dotenv()

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL ="qwen3:0.6b"

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
- `posts` is a partitioned table with per-year child tables named
  posts_y2008, posts_y2009, ... posts_y2024, plus posts_default. ALWAYS
  query `posts` itself with a creationdate filter (e.g. WHERE creationdate
  >= '2023-01-01' AND creationdate < '2024-01-01') -- NEVER query a
  posts_yXXXX table by name directly. Postgres prunes to the right
  partition automatically when you filter on creationdate against the
  parent; querying a child table directly skips that and silently
  produces wrong or incomplete results for anything spanning more than
  one partition.
- For tag-based FILTERING to a specific tag (e.g. "posts about python",
  "users who answered questions about python"), JOIN post_tags (post_id,
  tag) instead of using posts.tags LIKE '%python%'. The LIKE pattern
  forces a slow scan across a scattered text column even with a trigram
  index; post_tags.tag is a plain indexed equality lookup and is much
  faster. Example: JOIN post_tags ON post_tags.post_id = posts.id AND
  post_tags.tag = 'python'.
- For questions RANKING or COUNTING across ALL tags (e.g. "top 5 tags by
  number of posts", "how many posts are tagged javascript"), use the
  `tags` table's pre-computed `count` column instead of aggregating over
  post_tags. post_tags has ~71M rows with one row per (post, tag) pair --
  GROUP BY over all of it is a full-table aggregate and can approach the
  statement timeout, whereas `tags.count` already holds the answer.
  Example: SELECT tagname, count FROM tags ORDER BY count DESC LIMIT 5.
  Only use post_tags directly when the question needs something `tags`
  doesn't have, e.g. joining tag membership to another table's rows.
""".strip()


def summarize_turn(existing_summary: str | None, turn: dict)-> str:
    prompt= f'''
    Existing summary so far (may be empty):{existing_summary or "(none yet)"}

    new turn to fold in :
    q: {turn['question']}
    sql:{turn['sql']}
    (returned {turn['row_count']}rows)

    produce an updated , concise (2-4 sentences summary of the whole conversation , including this new turn . focus on what topics/ filters/time ranges the user has asked about and not exact sql)'''

    response = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)

    if response.text is None:
        return existing_summary or ""
    return response.text.strip()
    
class SQLGenerationError(Exception):
    '''raised when gemini's response isnt usable sql at all
    -- (empty response , safety- filtered, or effectively refusal)'''


def _generate_with_ollama(user_message: str)-> str:
    # local fall back for gemini api key quota 
    resp = requests.post(OLLAMA_URL,json={
        'model' : OLLAMA_MODEL,
        "prompt" : f'{SYSTEM_PROMPT}\n\n{user_message}',
        'stream': False,
    }, timeout=60)
    
    resp.raise_for_status()
    text = resp.json().get('response','')
    if not text:
        raise SQLGenerationError("ollama fallback returned no text")
    return text.strip()

def generate_sql(question: str, previous_error: str | None = None, history: list | None = None, history_summary: str | None = None) -> str:
    schema_text = render_schema_ddl(get_schema())
    conversation_context = ""
    if history_summary:
        conversation_context += f"Summary of earlier conversation:\n{history_summary}\n\n"
    if history:
        conversation_context += "conversation so far :\n"
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
    try:
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
        
    except (APIError,SQLGenerationError) as e:
        print( f'[fallback] Gemini failed ({e}) -- falling back to ollama ({OLLAMA_MODEL})')
        sql = _generate_with_ollama(user_message)
    if sql.startswith("```"):
            sql = sql.strip("`").removeprefix("sql").strip()
            
    if not sql:
            raise SQLGenerationError ('gemini returned a empty response after cleanup')
    return sql




if __name__ == "__main__":
    test_question = "How many questions were posted in 2023?"
    sql = generate_sql(test_question)
    print(sql)
