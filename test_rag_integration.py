#!/usr/bin/env python3
"""
Test script para verificar integração do RAG MCP Server
"""
import asyncio
import logging
from apps.orchestrator.mcp_client import MCPOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_rag_integration():
    """Testa integração com RAG server"""

    orchestrator = MCPOrchestrator()

    try:
        # 1. Inicializa e conecta ao servidor
        logger.info("=" * 60)
        logger.info("STEP 1: Initializing MCP Orchestrator")
        logger.info("=" * 60)
        await orchestrator.initialize()

        # 2. Lista tools disponíveis
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: Listing available tools")
        logger.info("=" * 60)
        tools = await orchestrator.get_tools()
        logger.info(f"Found {len(tools)} tools:")
        for tool in tools:
            logger.info(f"  - {tool['name']}: {tool['description']}")

        # 3. Testa get_collection_stats
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: Testing get_collection_stats")
        logger.info("=" * 60)
        stats = await orchestrator.execute_tool("get_collection_stats", {})
        logger.info(f"Collection stats: {stats}")

        # 4. Testa file_search
        logger.info("\n" + "=" * 60)
        logger.info("STEP 4: Testing file_search")
        logger.info("=" * 60)

        test_queries = [
            "Quais são os planos e preços?",
            "Como funciona o agendamento?",
            "FAQ sobre atendimento"
        ]

        for query in test_queries:
            logger.info(f"\nSearching for: '{query}'")
            result = await orchestrator.execute_tool(
                "file_search",
                {
                    "query": query,
                    "top_k": 3,
                    "min_score": 0.0
                }
            )

            logger.info(f"Found {result['count']} results:")
            for i, res in enumerate(result['results'], 1):
                logger.info(f"\n  Result {i}:")
                logger.info(f"    Score: {res['score']}")
                logger.info(f"    Source: {res['source']}")
                logger.info(f"    Content: {res['content'][:100]}...")

        logger.info("\n" + "=" * 60)
        logger.info("SUCCESS: All tests passed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"ERROR: Test failed: {e}", exc_info=True)
        raise

    finally:
        # Cleanup
        logger.info("\nShutting down...")
        await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(test_rag_integration())
