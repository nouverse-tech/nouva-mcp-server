import os
import sys
import json
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from util.load_config import load_memory_config
from db.analytics_repo import ensure_schema


def get_db_connection():
    try:
        import psycopg2
    except ImportError as e:
        raise ImportError("psycopg2 is required for database operations. Install dependencies from requirements.txt.") from e

    config = load_memory_config()
    db_config = config.get("database", {})

    db_url = db_config.get("url", "").strip()
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        db_host = db_config.get("host", "localhost")
        db_port = db_config.get("port", 5432)
        db_name = db_config.get("name", "postgres")
        db_user = db_config.get("user", "postgres")
        db_pass = db_config.get("password", "")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass
        )
    conn.set_client_encoding("UTF8")
    return conn


def get_ollama_embeddings(inputs):
    config = load_memory_config()
    embedding_config = config.get("embedding", {})

    embedding_url = embedding_config.get("url", "http://localhost:11434")
    model = embedding_config.get("model", "bge-m3:latest")

    is_single = isinstance(inputs, str)
    if is_single:
        inputs = [inputs]

    try:
        res = requests.post(f"{embedding_url}/api/embed", json={
            "model": model,
            "input": inputs
        }, timeout=300)
        res.raise_for_status()
        embeddings = res.json()["embeddings"]
        return embeddings[0] if is_single else embeddings
    except Exception as e:
        print(f"❌ Error generating embeddings (URL: {embedding_url}, model: {model}): {e}")
        raise e


def chunk_markdown(text, max_chunk_size=1000, overlap=100):
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(para) > max_chunk_size:
                start = 0
                while start < len(para):
                    end = start + max_chunk_size
                    chunks.append(para[start:end])
                    start += max_chunk_size - overlap
                current_chunk = ""
            else:
                current_chunk = para
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def sync_file_to_vector_db(document_path, file_content, metadata):
    chunks = chunk_markdown(file_content)
    if not chunks:
        print(f"⏭️ No chunks generated for {document_path}.")
        return False

    print(f"🔄 Generating embeddings for {len(chunks)} chunks of {document_path}...")
    embeddings = get_ollama_embeddings(chunks)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM nouva_memories WHERE document_path = %s;", (document_path,))
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                "INSERT INTO nouva_memories (document_path, chunk_index, content, embedding, metadata) VALUES (%s, %s, %s, %s, %s);",
                (document_path, idx, chunk, emb, json.dumps(metadata))
            )
        conn.commit()
        print(f"✅ Successfully synced {document_path} to pgvector database.")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to sync {document_path} to pgvector: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def delete_file_from_vector_db(document_path):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM nouva_memories WHERE document_path = %s;", (document_path,))
        conn.commit()
        print(f"🗑️ Deleted {document_path} from pgvector database.")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to delete {document_path} from pgvector: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def vector_search(query_text, limit=10):
    query_emb = get_ollama_embeddings(query_text)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT document_path, content, embedding <=> %s::vector AS distance, metadata
            FROM nouva_memories
            ORDER BY distance ASC
            LIMIT %s;
            """,
            (query_emb, limit)
        )
        rows = cur.fetchall()

        results = []
        for row in rows:
            doc_path, content, distance, metadata = row
            score = 1.0 - distance

            results.append({
                "text": content,
                "score": score,
                "metadata": metadata or {}
            })
        return results
    except Exception as e:
        print(f"❌ Vector search error: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def ensure_daily_summaries_table(conn=None):
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    try:
        ensure_schema(conn)
    finally:
        if close_conn:
            conn.close()
