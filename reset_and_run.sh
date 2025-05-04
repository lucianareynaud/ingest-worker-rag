#!/bin/bash
echo "Resetting all indexed documents..."
docker-compose run ingest-worker python reset_documents.py

echo ""
echo "Now reprocessing all documents with text sanitization..."
docker-compose run ingest-worker python process_pdfs.py 