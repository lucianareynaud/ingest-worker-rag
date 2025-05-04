#!/usr/bin/env python3
import os
import io
import sys
import numpy as np
import fitz                         # PyMuPDF
from PIL import Image
import pytesseract
from sentence_transformers import SentenceTransformer
from supabase import create_client
from dotenv import load_dotenv
import regex as re
import unicodedata

def sanitize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[^\p{L}0-9 \.,;:?!\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text

# 1) Load config
load_dotenv()
URL      = os.getenv("SUPABASE_URL")
KEY      = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
BUCKET   = os.getenv("STORAGE_BUCKET", "manuals")
MODEL    = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
CHUNK_SZ = int(os.getenv("CHUNK_SIZE", 512))
OVERLAP  = int(os.getenv("CHUNK_OVERLAP", 64))
DOMAIN   = os.getenv("DOMAIN", "general")

# 2) Init clients
supabase = create_client(URL, KEY)
embedder = SentenceTransformer(MODEL)

def detect_new_pdfs():
    """Find PDF files in the storage bucket and register them in documents table if they don't exist."""
    # Get all PDFs from storage
    storage_files = supabase.storage.from_(BUCKET).list()
    pdf_files = [f["name"] for f in storage_files if f["name"].endswith(".pdf")]
    
    print(f"[INFO] Found {len(pdf_files)} PDF files in storage bucket '{BUCKET}'")
    
    # Get all paths already in documents table
    result = supabase.table("documents").select("path").execute()
    registered_paths = set(item["path"] for item in result.data)
    
    # Find PDFs not in documents table yet
    new_pdfs = [pdf for pdf in pdf_files if pdf not in registered_paths]
    
    if new_pdfs:
        print(f"[INFO] Registering {len(new_pdfs)} new PDFs for processing: {new_pdfs}")
        # Add new PDFs to documents table
        for pdf in new_pdfs:
            supabase.table("documents").insert({"path": pdf, "indexed": False}).execute()
        print(f"[INFO] {len(new_pdfs)} new PDFs registered successfully")
    else:
        print("[INFO] No new PDFs to register")
    
    return new_pdfs

def list_unprocessed_pdfs():
    """Return list of file names that still lack an indexed_at flag."""
    # Query your 'documents' table to see which ones are already indexed:
    resp = supabase.table("documents").select("path").eq("indexed", False).execute()
    pending = [item["path"] for item in resp.data]
    
    print(f"[INFO] Found {len(pending)} unprocessed PDFs in documents table")
    return pending

def mark_indexed(path):
    """Mark document as indexed in database."""
    supabase.table("documents") \
      .update({"indexed": True, "indexed_at": "now()"}) \
      .eq("path", path) \
      .execute()

def extract_text(pdf_bytes: bytes):
    """Extract text (native or OCR) from every page."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for p in doc:
        txt = p.get_text().strip()
        if txt:
            pages.append(txt)
        else:
            try:
                pix = p.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Try Portuguese first, if it fails, fallback to English
                try:
                    ocr_text = pytesseract.image_to_string(img, lang="por").strip()
                    print("[INFO] Used Portuguese OCR")
                except Exception as e:
                    print(f"[WARN] Portuguese OCR failed: {str(e)}, falling back to English")
                    ocr_text = pytesseract.image_to_string(img, lang="eng").strip()
                    print("[INFO] Used English OCR")
                
                pages.append(ocr_text)
            except Exception as e:
                print(f"[WARN] OCR failed on page: {str(e)}")
                # Add empty string to maintain page count
                pages.append("")
    return pages

def chunkify(text: str):
    tokens = text.split()
    for i in range(0, len(tokens), CHUNK_SZ - OVERLAP):
        yield " ".join(tokens[i : i + CHUNK_SZ])

def process(path: str):
    """Process a single PDF: download, extract text, chunk, embed, and store."""
    print(f"[START] Processing {path}")
    
    # 1. download
    response = supabase.storage.from_(BUCKET).download(path)
    pdf_bytes = response
    print(f"[INFO] Downloaded {path}, size: {len(pdf_bytes)/1024:.2f} KB")
    
    # 2. extract & chunk
    all_chunks = []
    pages = extract_text(pdf_bytes)
    print(f"[INFO] Extracted {len(pages)} pages from {path}")
    
    for page in pages:
        if page.strip():  # Only process non-empty pages
            all_chunks.extend(list(chunkify(page)))
    print(f"[INFO] Created {len(all_chunks)} chunks from {path}")
    
    if not all_chunks:
        print(f"[WARN] No text content found in {path}")
        mark_indexed(path)
        return
    
    # 3. embed & insert
    for idx, chunk in enumerate(all_chunks):
        clean = sanitize_text(chunk)
        vec = embedder.encode(clean).astype(np.float32).tolist()
        supabase.table("document_chunks").insert({
            "domain": DOMAIN,
            "storage_path": path,
            "chunk_id": idx,
            "content": chunk,
            "embedding": vec
        }).execute()
    
    # 4. mark done
    mark_indexed(path)
    print(f"[FINISH] Successfully processed {path}")

def main():
    """Main entry point for the script."""
    print(f"[INFO] Starting PDF ingestion job at BUCKET={BUCKET}")
    
    if not URL or not KEY:
        print("[ERROR] Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env file")
        return 1
    
    # Register any new PDFs found in storage
    new_pdfs = detect_new_pdfs()
    
    # Get list of PDFs that need processing
    pdfs = list_unprocessed_pdfs()
    
    if not pdfs:
        print("[INFO] No PDFs found to process")
        return 0
    
    print(f"[INFO] Found {len(pdfs)} PDFs to process")
    
    success_count = 0
    error_count = 0
    
    for pdf in pdfs:
        try:
            process(pdf)
            success_count += 1
        except Exception as e:
            error_count += 1
            print(f"[ERROR] Failed to process {pdf}: {str(e)}")
    
    print(f"[SUMMARY] Processed {success_count} PDFs successfully, {error_count} errors")
    
    # Return non-zero exit code if any PDFs failed processing
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main()) 