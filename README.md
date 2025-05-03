# PDF Ingestion Worker for RAG

A Python-based worker that automatically processes PDFs stored in Supabase storage, extracts text (with OCR fallback), chunks the content, creates embeddings, and stores them in a vector database for Retrieval Augmented Generation (RAG).

## System Architecture

```mermaid
graph TD
    subgraph "Supabase Cloud"
        A[Storage: PDF Bucket] --> B[PDF Files]
        D[(PostgreSQL Database)]
        D --> E[documents table]
        D --> F[document_chunks table]
    end
    
    subgraph "Ingest Worker"
        G[process_pdfs.py] --> H[Detect New PDFs]
        H --> I[Extract Text]
        I --> J[Chunk Text]
        J --> K[Generate Embeddings]
        K --> L[Store Vectors]
    end
    
    B -- Download --> I
    H -- Register --> E
    L -- Store --> F
    
    subgraph "Client Application"
        M[User Query] --> N[Vector Search]
        N -- Semantic Similarity --> F
        F -- Relevant Chunks --> O[RAG Result]
    end
```

## Features

- Processes PDFs stored in Supabase storage bucket
- Uses PyMuPDF for native PDF text extraction
- Falls back to OCR (pytesseract) for image-based PDFs
- Chunks text with configurable size and overlap
- Creates embeddings using a specified model (default: intfloat/multilingual-e5-small)
- Stores vectors in Supabase for RAG applications
- Automatically registers new PDFs added to the storage bucket

## Vector Embedding Example

When a PDF is processed, the text is extracted, chunked, and transformed into vector embeddings. For example:

```
Chunk: "The Honda Fit is a subcompact car manufactured by Honda. The Fit features a spacious interior and excellent fuel economy..."

Embedding (first 10 values of 384-dimension vector):
[-0.0321, 0.0512, -0.0244, 0.0711, 0.0023, -0.0431, 0.0142, 0.0864, -0.0013, 0.0331, ...]
```

These dense vector representations capture the semantic meaning of text chunks, enabling powerful similarity searches for retrieval-augmented generation.

### Embeddings in Supabase

Below is an example of how the embeddings appear in the Supabase database after processing:

![Vector Embeddings in Supabase](embeddings-print.png)

Each row represents a chunk of text from a PDF, with its corresponding vector embedding that can be used for semantic search.

## Setup Options

You can run this project either using Docker (recommended) or directly with Python.

### Option 1: Running with Docker (Recommended)

1. Make sure you have Docker and Docker Compose installed
2. Ensure your `.env` file is properly configured (see Environment Variables section)
3. Run the container:

```bash
# For manual processing (recommended)
docker-compose run ingest-worker python process_pdfs.py

# Or use the convenience script
./run.sh
```

### Option 2: Running with Python Virtual Environment

#### 1. Create a Python virtual environment

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

#### 2. Install system dependencies

You'll need to install Tesseract OCR:

```bash
# On Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y tesseract-ocr libtesseract-dev tesseract-ocr-por

# On macOS
brew install tesseract

# On Windows
# Download and install from: https://github.com/UB-Mannheim/tesseract/wiki
```

#### 3. Run the worker manually

```bash
python process_pdfs.py
```

## Environment Variables

Create a `.env` file in the project directory with the following variables:

```
EMBEDDING_MODEL=intfloat/multilingual-e5-small
CHUNK_SIZE=512
CHUNK_OVERLAP=64
DOMAIN=automotive
SUPABASE_URL="your-supabase-url"
SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key"
STORAGE_BUCKET="manuals"
DATABASE_URL="postgresql://postgres:password@db.example.com:5432/postgres"
```

Required variables:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase service role key (with database access)
- `STORAGE_BUCKET`: Name of the bucket where PDFs are stored (default: "manuals")

## Usage

### Manual Processing

To process PDFs manually:

1. Upload PDF files to your Supabase storage bucket ("manuals" by default)
2. Run the processing script:

```bash
# If using Docker
docker-compose run ingest-worker python process_pdfs.py

# If using Python directly
python process_pdfs.py
```

The script will:
1. Detect any new PDFs in the storage bucket
2. Register them in the `documents` table
3. Process each PDF (extract text, create chunks, generate embeddings)
4. Store the vectors in the `document_chunks` table

## Database Schema

The system requires two tables in your Supabase database:

1. `documents` - Tracks PDF processing status
2. `document_chunks` - Stores text chunks and their embeddings

The schema is defined in the Supabase SQL:

```sql
-- Table to track ingestion status
CREATE TABLE IF NOT EXISTS documents (
  path        TEXT PRIMARY KEY,
  uploaded_at TIMESTAMPTZ DEFAULT now(),
  indexed     BOOLEAN DEFAULT false,
  indexed_at  TIMESTAMPTZ
);

-- Vector table
CREATE TABLE IF NOT EXISTS document_chunks (
  domain       TEXT,
  storage_path TEXT,
  chunk_id     INT,
  content      TEXT,
  embedding    VECTOR(384)
);
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 