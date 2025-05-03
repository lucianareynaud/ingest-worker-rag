#!/usr/bin/env python3
"""
Script para processar PDFs manualmente.
Execute este script após adicionar novos PDFs ao bucket do Supabase.
"""
import os
import sys
from ingest_worker import main, detect_new_pdfs

if __name__ == "__main__":
    print("=== PDF Processing Tool ===")
    print("Este script irá:")
    print("1. Detectar novos PDFs no bucket Supabase")
    print("2. Registrá-los na tabela 'documents'")
    print("3. Processar os PDFs para criar embeddings vetoriais")
    print()
    
    # Detectar e registrar novos PDFs
    detect_new_pdfs()
    
    # Processar todos os PDFs não indexados
    exit_code = main()
    
    if exit_code == 0:
        print("\n✅ Processamento concluído com sucesso!")
    else:
        print("\n❌ Processamento concluído com erros. Verifique os logs acima.")
    
    sys.exit(exit_code) 