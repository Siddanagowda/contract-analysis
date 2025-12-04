"""
Debug script to check what's in the database chunks
"""
import sqlite3
from sqlite_rag import SQLiteOpenAIRAG

rag = SQLiteOpenAIRAG()

conn = sqlite3.connect(rag.db_path)
cursor = conn.cursor()

# Check document chunks
cursor.execute('SELECT COUNT(*) FROM document_chunks')
count = cursor.fetchone()[0]
print(f"Total chunks in database: {count}\n")

if count > 0:
    cursor.execute('SELECT chunk_id, page_number, LENGTH(chunk_text) as text_length FROM document_chunks LIMIT 10')
    chunks = cursor.fetchall()
    
    print("First 10 chunks:")
    for chunk_id, page_num, text_len in chunks:
        print(f"  Chunk {chunk_id}, Page {page_num}, Text length: {text_len}")
    
    # Get actual text from first chunk
    cursor.execute('SELECT chunk_text FROM document_chunks LIMIT 1')
    first_chunk = cursor.fetchone()
    if first_chunk:
        print(f"\nFirst chunk text preview:")
        print(f"{first_chunk[0][:500]}...")

conn.close()
