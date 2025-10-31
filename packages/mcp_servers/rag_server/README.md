# RAG MCP Server

MCP Server para busca semântica em documentos.

## Setup

### 1. Indexar documentos

```bash
# Indexa documentos comerciais
python packages/rag/ingest.py docs/comercial/

# Ou arquivo específico
python packages/rag/ingest.py docs/comercial/precos.md
```

### 2. Configurar variáveis

```bash
export CHROMA_PERSIST_DIR=./data/chroma_db
export OPENAI_API_KEY=sk-...
```

### 3. Testar standalone

```bash
python packages/mcp_servers/rag_server/server.py
```

## Tools Disponíveis

### file_search
Busca semântica em documentos.

```json
{
  "query": "Quanto custa o plano professional?",
  "top_k": 5,
  "min_score": 0.7
}
```

**Retorna:**
```json
{
  "query": "Quanto custa o plano professional?",
  "results": [
    {
      "content": "Plano Professional: R$ 299/mês...",
      "source": "docs/comercial/precos.md",
      "score": 0.92,
      "metadata": {...}
    }
  ],
  "count": 1
}
```

### get_collection_stats
Retorna estatísticas da base.

```json
{}
```

**Retorna:**
```json
{
  "collection_name": "alabia_docs",
  "document_count": 47,
  "status": "ready"
}
```

## Uso via MCP

```python
from mcp import ClientSession, StdioServerParameters

server = StdioServerParameters(
    command="python",
    args=["packages/mcp_servers/rag_server/server.py"],
    env={
        "CHROMA_PERSIST_DIR": "./data/chroma_db",
        "OPENAI_API_KEY": "sk-..."
    }
)

async with ClientSession(server) as session:
    result = await session.call_tool("file_search", {"query": "preços"})
```
