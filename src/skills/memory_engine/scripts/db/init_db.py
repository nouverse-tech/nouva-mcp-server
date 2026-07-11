import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db import db_helper


def init_db():
    print("🔌 Connecting to database via memory_config.json...")
    conn = db_helper.get_db_connection()
    cur = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS nouva_memories (
            id SERIAL PRIMARY KEY,
            document_path TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1024),
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS nouva_memories_embedding_idx
        ON nouva_memories USING hnsw (embedding vector_cosine_ops);
    """)

    db_helper.ensure_daily_summaries_table(conn)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized successfully.")


if __name__ == "__main__":
    init_db()

