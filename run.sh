#!/bin/bash
echo "Building and running ingest-worker Docker container for PDF processing..."
docker-compose run ingest-worker python process_pdfs.py 