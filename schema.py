import json
from sqlalchemy import inspect
from database import engine
from relationships import RELATIONSHIPS

def get_schema():
    inspector = inspect (engine)
    schema = {}
    
    for tabel_name in inspector.get_table_names(schema='public'):
        columns = inspector.get_columns(tabel_name, schema='public')
        pk = inspector.get_pk_constraint(tabel_name, schema='public')
        indexes = inspector.get_indexes(tabel_name, schema='public')
        
        schema[tabel_name] = {
            'columns':[
                {'name': c['name'], 'type': str(c['type']), 'nullable': c['nullable']} for c in columns
            ],
            'primary_key': pk.get('constrained_columns', []),
            'indexes': [ idx['name'] for idx in indexes]
        }

    for rel in RELATIONSHIPS:
        schema[rel['from_table']].setdefault('foreign_keys', []).append(
            {'column': rel['from_column'], 'references': f"{rel['to_table']}.{rel['to_column']}"}
        )

    return schema

if __name__ == "__main__":
    schema = get_schema()
    print(json.dumps(schema, indent=4))
    print(f'found {len(schema)} tables: {list(schema.keys())}')
    print("schema extraction completed successfully.")