#!/usr/bin/env python3
"""
RAG MCP Server
Busca semântica em documentos via Model Context Protocol
"""
import asyncio
import logging
import os
from typing import List
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MCP imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: MCP not installed. Run: pip install mcp")
    exit(1)

# ChromaDB e OpenAI
try:
    import chromadb
    from chromadb.config import Settings
    from openai import OpenAI
except ImportError:
    print("ERROR: Dependencies not installed. Run: pip install chromadb openai")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Server MCP
server = Server("alabia-rag-server")


class RAGClient:
    """Cliente para busca semântica em ChromaDB"""

    def __init__(
        self,
        chroma_persist_dir: str,
        collection_name: str = "alabia_docs",
        openai_api_key: str = None,
        embedding_model: str = "text-embedding-3-small"
    ):
        """
        Inicializa cliente RAG

        Args:
            chroma_persist_dir: Diretório do ChromaDB
            collection_name: Nome da coleção
            openai_api_key: API key OpenAI
            embedding_model: Modelo de embedding
        """
        self.collection_name = collection_name
        self.embedding_model = embedding_model

        # OpenAI
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.openai_client = OpenAI(api_key=api_key)

        # ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        try:
            self.collection = self.chroma_client.get_collection(name=collection_name)
            logger.info(f"Loaded collection '{collection_name}' with {self.collection.count()} documents")
        except Exception as e:
            logger.warning(f"Collection '{collection_name}' not found. Creating empty collection.")
            self.collection = self.chroma_client.create_collection(
                name=collection_name,
                metadata={"description": "Alabia knowledge base"}
            )

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

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0
    ) -> dict:
        """
        Busca semântica em documentos

        Args:
            query: Query de busca
            top_k: Número de resultados
            min_score: Score mínimo (similaridade)

        Returns:
            Resultados da busca
        """
        try:
            # Cria embedding da query
            query_embedding = self._create_embedding(query)

            # Busca no Chroma
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )

            # Formata resultados
            if not results['documents'] or not results['documents'][0]:
                return {
                    "query": query,
                    "results": [],
                    "count": 0
                }

            formatted_results = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                # Converte distance em score (quanto menor a distância, maior o score)
                # ChromaDB usa distância euclidiana
                score = 1.0 / (1.0 + distance)

                if score >= min_score:
                    formatted_results.append({
                        "content": doc,
                        "source": metadata.get("source", "unknown"),
                        "score": round(score, 3),
                        "metadata": metadata
                    })

            logger.info(f"Found {len(formatted_results)} results for query: '{query[:50]}...'")

            return {
                "query": query,
                "results": formatted_results,
                "count": len(formatted_results)
            }

        except Exception as e:
            logger.error(f"Error searching: {e}", exc_info=True)
            raise

    def get_stats(self) -> dict:
        """Retorna estatísticas da coleção"""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "status": "ready" if count > 0 else "empty"
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "collection_name": self.collection_name,
                "status": "error",
                "error": str(e)
            }


# Cliente global
rag_client = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Lista tools disponíveis"""
    return [
        Tool(
            name="file_search",
            description="Busca semântica em documentos da base de conhecimento da Alabia (preços, FAQ, documentação)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Texto de busca ou pergunta"
                    },
                    "top_k": {
                        "type": "number",
                        "description": "Número de resultados a retornar (padrão: 5)"
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Score mínimo de relevância 0-1 (padrão: 0.0)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_collection_stats",
            description="Retorna estatísticas da base de conhecimento (número de documentos indexados)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Executa tool"""
    global rag_client

    if not rag_client:
        return [TextContent(type="text", text="ERROR: RAG client not initialized")]

    try:
        if name == "file_search":
            query = arguments.get("query")
            top_k = arguments.get("top_k", 5)
            min_score = arguments.get("min_score", 0.0)

            result = rag_client.search(query=query, top_k=top_k, min_score=min_score)

        elif name == "get_collection_stats":
            result = rag_client.get_stats()

        else:
            return [TextContent(type="text", text=f"ERROR: Unknown tool: {name}")]

        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]

    except Exception as e:
        logger.error(f"Error executing {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"ERROR: {str(e)}")]


async def main():
    """Main entry point"""
    global rag_client

    # Configuração
    chroma_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
    collection_name = os.getenv("CHROMA_COLLECTION", "alabia_docs")

    logger.info(f"Initializing RAG Server")
    logger.info(f"ChromaDB dir: {chroma_dir}")
    logger.info(f"Collection: {collection_name}")

    # Inicializa RAG client
    rag_client = RAGClient(
        chroma_persist_dir=chroma_dir,
        collection_name=collection_name
    )

    stats = rag_client.get_stats()
    logger.info(f"RAG Server ready. Stats: {stats}")

    # Roda servidor MCP via stdio
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
