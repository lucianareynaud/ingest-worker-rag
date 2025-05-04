#!/usr/bin/env python3
"""
Script to reset indexed documents and delete their existing chunks
so they can be reprocessed with the new text sanitization.
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load config
load_dotenv()
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Init client
supabase = create_client(URL, KEY)

def reset_all_documents():
    """Reset all documents to unindexed state and delete their chunks."""
    # Get all documents that are currently indexed
    result = supabase.table("documents").select("path").eq("indexed", True).execute()
    indexed_docs = [item["path"] for item in result.data]
    
    if not indexed_docs:
        print("[INFO] No indexed documents found to reset")
        return 0
    
    print(f"[INFO] Found {len(indexed_docs)} indexed documents to reset")
    
    # Delete chunks for each document
    chunks_deleted = 0
    for doc_path in indexed_docs:
        # Delete document chunks
        result = supabase.table("document_chunks").delete().eq("storage_path", doc_path).execute()
        deleted_count = len(result.data)
        chunks_deleted += deleted_count
        print(f"[INFO] Deleted {deleted_count} chunks for document: {doc_path}")
        
        # Reset indexed status
        supabase.table("documents").update({"indexed": False, "indexed_at": None}).eq("path", doc_path).execute()
        print(f"[INFO] Reset indexed status for document: {doc_path}")
    
    print(f"[SUMMARY] Reset {len(indexed_docs)} documents, deleted {chunks_deleted} chunks")
    print("[NEXT] Run 'run.sh' to reprocess all documents with the new sanitization")
    return 0

if __name__ == "__main__":
    if not URL or not KEY:
        print("[ERROR] Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env file")
        sys.exit(1)
    
    try:
        reset_status = reset_all_documents()
        sys.exit(reset_status)
    except Exception as e:
        print(f"[ERROR] Failed to reset documents: {str(e)}")
        sys.exit(1) 