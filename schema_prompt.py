# Renders the reflected schema (schema.py) as CREATE TABLE-style DDL text --
# the format an LLM is most reliably trained to read for SQL generation --
# instead of handing it the raw JSON. See PROJECT_PROGRESS.md for the
# reasoning behind DDL over JSON.

from schema import get_schema
from lookups import LOOKUPS


def render_schema_ddl(schema: dict) -> str:
    blocks = []

    for table_name, table in schema.items():
        col_lines = []
        for col in table["columns"]:
            nullable = "" if col["nullable"] else " NOT NULL"
            pk = " PRIMARY KEY" if col["name"] in table["primary_key"] else ""
            col_lines.append(f"    {col['name']} {col['type']}{nullable}{pk}")

        block = f"CREATE TABLE {table_name} (\n" + ",\n".join(col_lines) + "\n);"

        # FK relationships as comments, not real FOREIGN KEY clauses --
        # Stack Overflow's dump doesn't enforce these (orphaned references
        # exist, e.g. deleted users), so a real constraint would overstate
        # the guarantee to the model.
        for fk in table.get("foreign_keys", []):
            block += f"\n-- {table_name}.{fk['column']} references {fk['references']}"

        # Lookup-code columns have no meaning in the schema itself --
        # spell out what each integer means so the model doesn't guess.
        for col_name, codes in LOOKUPS.get(table_name, {}).items():
            code_str = ", ".join(f"{k}={v}" for k, v in codes.items())
            block += f"\n-- {table_name}.{col_name} values: {code_str}"

        blocks.append(block)

    return "\n\n".join(blocks)


if __name__ == "__main__":
    print(render_schema_ddl(get_schema()))
