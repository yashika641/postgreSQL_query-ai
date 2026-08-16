import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
load_dotenv()

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

def test_connection():
    with engine.connect() as conn:
        row= conn.execute(text("SELECT reltuples::bigint FROM pg_class WHERE relname = 'posts'"))
        print("connected . approxrows in posts table:", row.scalar())
        
if __name__ == "__main__":
    test_connection()