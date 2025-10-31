#!/usr/bin/env python3
"""
RAG Document Ingestion
Indexa documentos (PDFs, TXTs, MDs) no ChromaDB com embeddings OpenAI
"""
import os
import logging
from pathlib import Path
from typing import List, Dict
import chromadb
from chromadb.config import Settings

# OpenAI para embeddings
from openai import OpenAI

# PDF parsing
try:
    from pypdf import PdfReader
except ImportError:
    print("WARNING: pypdf not installed. PDF support disabled.")
    PdfReader = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentIngester:
    """Ingestão de documentos para RAG"""

    def __init__(
        self,
        chroma_persist_dir: str = "./data/chroma_db",
        collection_name: str = "alabia_docs",
        openai_api_key: str = None,
        embedding_model: str = "text-embedding-3-small"
    ):
        """
        Inicializa ingester

        Args:
            chroma_persist_dir: Diretório do ChromaDB
            collection_name: Nome da coleção
            openai_api_key: API key OpenAI
            embedding_model: Modelo de embedding
        """
        self.chroma_persist_dir = chroma_persist_dir
        self.collection_name = collection_name
        self.embedding_model = embedding_model

        # OpenAI client
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.openai_client = OpenAI(api_key=api_key)

        # ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        # Collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Alabia knowledge base"}
        )

        logger.info(f"Ingester initialized. Collection: {collection_name}")

    def _create_embedding(self, text: str) -> List[float]:
        """Cria embedding com OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            raise

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 512,
        overlap: int = 50
    ) -> List[str]:
        """
        Divide texto em chunks com overlap

        Args:
            text: Texto para dividir
            chunk_size: Tamanho do chunk em caracteres
            overlap: Overlap entre chunks

        Returns:
            Lista de chunks
        """
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Tenta quebrar em ponto final ou parágrafo
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)

                if break_point > chunk_size * 0.5:  # Se encontrou ponto razoável
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1

            chunks.append(chunk.strip())
            start = end - overlap

        return [c for c in chunks if c]  # Remove vazios

    def _read_text_file(self, filepath: Path) -> str:
        """Lê arquivo de texto"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return ""

    def _read_pdf(self, filepath: Path) -> str:
        """Lê arquivo PDF"""
        if not PdfReader:
            logger.warning(f"PDF support not available. Skipping {filepath}")
            return ""

        try:
            reader = PdfReader(filepath)
            text = []
            for page in reader.pages:
                text.append(page.extract_text())
            return "\n\n".join(text)
        except Exception as e:
            logger.error(f"Error reading PDF {filepath}: {e}")
            return ""

    def ingest_file(self, filepath: Path) -> int:
        """
        Ingere um arquivo

        Args:
            filepath: Caminho do arquivo

        Returns:
            Número de chunks indexados
        """
        logger.info(f"Ingesting file: {filepath}")

        # Determina tipo e lê conteúdo
        suffix = filepath.suffix.lower()

        if suffix == '.pdf':
            content = self._read_pdf(filepath)
        elif suffix in ['.txt', '.md']:
            content = self._read_text_file(filepath)
        else:
            logger.warning(f"Unsupported file type: {suffix}")
            return 0

        if not content:
            logger.warning(f"No content extracted from {filepath}")
            return 0

        # Divide em chunks
        chunks = self._chunk_text(content)
        logger.info(f"Created {len(chunks)} chunks from {filepath}")

        # Cria embeddings e indexa
        for i, chunk in enumerate(chunks):
            try:
                embedding = self._create_embedding(chunk)

                # ID único
                doc_id = f"{filepath.stem}_{i}"

                # Metadata
                metadata = {
                    "source": str(filepath),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "file_type": suffix
                }

                # Adiciona ao Chroma
                self.collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[metadata]
                )

                logger.debug(f"Indexed chunk {i+1}/{len(chunks)}")

            except Exception as e:
                logger.error(f"Error indexing chunk {i}: {e}")

        logger.info(f"✓ Indexed {len(chunks)} chunks from {filepath.name}")
        return len(chunks)

    def ingest_directory(self, dirpath: Path, recursive: bool = True) -> Dict[str, int]:
        """
        Ingere todos os arquivos de um diretório

        Args:
            dirpath: Diretório
            recursive: Buscar recursivamente

        Returns:
            Dict com estatísticas
        """
        logger.info(f"Ingesting directory: {dirpath}")

        stats = {
            "files_processed": 0,
            "chunks_indexed": 0,
            "errors": 0
        }

        # Padrão de arquivos suportados
        patterns = ['*.txt', '*.md', '*.pdf']

        for pattern in patterns:
            if recursive:
                files = dirpath.rglob(pattern)
            else:
                files = dirpath.glob(pattern)

            for filepath in files:
                try:
                    chunks = self.ingest_file(filepath)
                    stats["files_processed"] += 1
                    stats["chunks_indexed"] += chunks
                except Exception as e:
                    logger.error(f"Error processing {filepath}: {e}")
                    stats["errors"] += 1

        logger.info(f"Ingestion complete. Stats: {stats}")
        return stats

    def clear_collection(self):
        """Limpa toda a coleção"""
        logger.warning(f"Clearing collection: {self.collection_name}")
        self.chroma_client.delete_collection(self.collection_name)
        self.collection = self.chroma_client.create_collection(
            name=self.collection_name,
            metadata={"description": "Alabia knowledge base"}
        )
        logger.info("Collection cleared")


def main():
    """Main CLI"""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest documents into RAG")
    parser.add_argument(
        "path",
        help="File or directory to ingest"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear collection before ingesting"
    )
    parser.add_argument(
        "--chroma-dir",
        default="./data/chroma_db",
        help="ChromaDB directory"
    )

    args = parser.parse_args()

    # Inicializa ingester
    ingester = DocumentIngester(chroma_persist_dir=args.chroma_dir)

    # Clear se solicitado
    if args.clear:
        ingester.clear_collection()

    # Ingere
    path = Path(args.path)

    if path.is_file():
        chunks = ingester.ingest_file(path)
        print(f"✓ Indexed {chunks} chunks")
    elif path.is_dir():
        stats = ingester.ingest_directory(path)
        print(f"✓ Processed {stats['files_processed']} files")
        print(f"✓ Indexed {stats['chunks_indexed']} chunks")
        if stats['errors'] > 0:
            print(f"⚠ {stats['errors']} errors occurred")
    else:
        print(f"ERROR: Path not found: {path}")
        exit(1)


if __name__ == "__main__":
    main()
