"""
MCP Client - Gerenciador de MCP Servers
Conecta e gerencia múltiplos MCP servers (RAG, Calendar, Web Search)
"""
import logging
import asyncio
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

# MCP imports
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("ERROR: MCP not installed. Run: pip install mcp")
    raise

logger = logging.getLogger(__name__)


class MCPOrchestrator:
    """
    Orquestrador de MCP Servers

    Gerencia conexão com múltiplos MCP servers e fornece
    interface unificada para execução de tools.
    """

    def __init__(self):
        """Inicializa orquestrador"""
        self.servers: Dict[str, Dict[str, Any]] = {}  # name -> {session, stdio_context}
        self.tools: Dict[str, Dict[str, Any]] = {}  # tool_name -> tool_info
        self.server_for_tool: Dict[str, str] = {}  # tool_name -> server_name
        self.is_initialized = False

        logger.info("MCP Orchestrator created")

    async def initialize(self):
        """
        Inicializa e conecta todos os MCP servers

        Servidores disponíveis:
        - RAG Server (file_search)
        - Calendar Server (create_event, check_availability, list_events)
        - Web Search Server (web_search)
        """
        logger.info("Initializing MCP servers...")

        try:
            # RAG Server
            await self._connect_rag_server()

            # Calendar Server
            await self._connect_calendar_server()

            # Pipedrive Server
            await self._connect_pipedrive_server()

            # Web Search Server (TODO)
            # await self._connect_websearch_server()

            self.is_initialized = True
            logger.info(f"MCP initialized with {len(self.tools)} tools from {len(self.servers)} servers")

        except Exception as e:
            logger.error(f"Error initializing MCP servers: {e}", exc_info=True)
            raise

    async def _connect_rag_server(self):
        """Conecta ao RAG MCP Server"""
        server_name = "rag"

        try:
            logger.info(f"Connecting to RAG server...")

            # Caminho para o script do servidor
            project_root = Path(__file__).parent.parent.parent
            server_script = project_root / "packages" / "mcp_servers" / "rag_server" / "server.py"

            if not server_script.exists():
                raise FileNotFoundError(f"RAG server script not found: {server_script}")

            # Parâmetros do servidor stdio
            server_params = StdioServerParameters(
                command="python",
                args=[str(server_script)],
                env={
                    **os.environ,
                    "PYTHONPATH": str(project_root)
                }
            )

            # Conecta via stdio (é um context manager)
            stdio_context = stdio_client(server_params)
            read_stream, write_stream = await stdio_context.__aenter__()

            # Cria sessão MCP
            session = ClientSession(read_stream, write_stream)

            # Inicializa sessão
            await session.__aenter__()
            await session.initialize()

            # Armazena sessão e context manager para cleanup posterior
            self.servers[server_name] = {
                "session": session,
                "stdio_context": stdio_context
            }

            # Lista e registra tools
            tools_response = await session.list_tools()

            for tool in tools_response.tools:
                tool_dict = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                }
                self.tools[tool.name] = tool_dict
                self.server_for_tool[tool.name] = server_name
                logger.info(f"Registered tool: {tool.name} from {server_name}")

            logger.info(f"RAG server connected successfully with {len(tools_response.tools)} tools")

        except Exception as e:
            logger.error(f"Failed to connect to RAG server: {e}", exc_info=True)
            raise

    async def _connect_calendar_server(self):
        """Conecta ao Calendar MCP Server"""
        server_name = "calendar"

        try:
            logger.info(f"Connecting to Calendar server...")

            # Caminho para o script do servidor
            project_root = Path(__file__).parent.parent.parent
            server_script = project_root / "packages" / "mcp_servers" / "calendar_server" / "server.py"

            if not server_script.exists():
                raise FileNotFoundError(f"Calendar server script not found: {server_script}")

            # Parâmetros do servidor stdio
            server_params = StdioServerParameters(
                command="python",
                args=[str(server_script)],
                env={
                    **os.environ,
                    "PYTHONPATH": str(project_root)
                }
            )

            # Conecta via stdio (é um context manager)
            stdio_context = stdio_client(server_params)
            read_stream, write_stream = await stdio_context.__aenter__()

            # Cria sessão MCP
            session = ClientSession(read_stream, write_stream)

            # Inicializa sessão
            await session.__aenter__()
            await session.initialize()

            # Armazena sessão e context manager para cleanup posterior
            self.servers[server_name] = {
                "session": session,
                "stdio_context": stdio_context
            }

            # Lista e registra tools
            tools_response = await session.list_tools()

            for tool in tools_response.tools:
                tool_dict = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                }
                self.tools[tool.name] = tool_dict
                self.server_for_tool[tool.name] = server_name
                logger.info(f"Registered tool: {tool.name} from {server_name}")

            logger.info(f"Calendar server connected successfully with {len(tools_response.tools)} tools")

        except Exception as e:
            logger.error(f"Failed to connect to Calendar server: {e}", exc_info=True)
            raise

    async def _connect_pipedrive_server(self):
        """Conecta ao Pipedrive MCP Server"""
        server_name = "pipedrive"

        try:
            logger.info(f"Connecting to Pipedrive server...")

            project_root = Path(__file__).parent.parent.parent
            server_script = project_root / "packages" / "mcp_servers" / "pipedrive_simple" / "server.py"

            if not server_script.exists():
                raise FileNotFoundError(f"Pipedrive server script not found: {server_script}")

            server_params = StdioServerParameters(
                command="python",
                args=[str(server_script)],
                env={
                    **os.environ,
                    "PYTHONPATH": str(project_root)
                }
            )

            stdio_context = stdio_client(server_params)
            read_stream, write_stream = await stdio_context.__aenter__()

            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()

            self.servers[server_name] = {
                "session": session,
                "stdio_context": stdio_context
            }

            tools_response = await session.list_tools()

            for tool in tools_response.tools:
                tool_dict = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                }
                self.tools[tool.name] = tool_dict
                self.server_for_tool[tool.name] = server_name
                logger.info(f"Registered tool: {tool.name} from {server_name}")

            logger.info(f"Pipedrive server connected successfully with {len(tools_response.tools)} tools")

        except Exception as e:
            logger.error(f"Failed to connect to Pipedrive server: {e}", exc_info=True)
            raise

    async def get_tools(self) -> List[Dict[str, Any]]:
        """
        Retorna lista de todas as tools disponíveis

        Returns:
            Lista de tools no formato MCP
        """
        if not self.is_initialized:
            await self.initialize()

        return list(self.tools.values())

    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Executa uma tool específica

        Args:
            tool_name: Nome da tool
            tool_input: Parâmetros de entrada

        Returns:
            Resultado da execução

        Raises:
            ValueError: Se tool não existe
            Exception: Se erro na execução
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found. Available: {list(self.tools.keys())}")

        logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

        try:
            # Busca o servidor responsável pela tool
            server_name = self.server_for_tool.get(tool_name)
            if not server_name:
                raise ValueError(f"No server registered for tool: {tool_name}")

            server_info = self.servers.get(server_name)
            if not server_info:
                raise ValueError(f"Server '{server_name}' not connected")

            session = server_info["session"]

            # Executa via MCP
            result = await session.call_tool(tool_name, tool_input)

            # Extrai o conteúdo da resposta
            if result and hasattr(result, 'content') and len(result.content) > 0:
                import json
                text_content = result.content[0].text

                # Try to parse JSON
                try:
                    parsed_result = json.loads(text_content)
                except json.JSONDecodeError:
                    # If not JSON, treat as plain text error
                    logger.warning(f"Tool {tool_name} returned non-JSON: {text_content}")
                    parsed_result = {"error": text_content, "tool": tool_name}

                # Check if result contains error
                if isinstance(parsed_result, dict) and "error" in parsed_result:
                    logger.error(f"Tool {tool_name} returned error: {parsed_result['error']}")
                    # Return error result instead of raising - let Claude handle it
                    return parsed_result

                logger.info(f"Tool {tool_name} executed successfully")
                return parsed_result
            else:
                logger.warning(f"Tool {tool_name} returned empty result")
                return {"status": "success", "result": None}

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            # Return error as dict instead of raising - let Claude see the error
            return {"error": str(e), "tool": tool_name, "input": tool_input}


    async def shutdown(self):
        """Encerra conexões com MCP servers"""
        logger.info("Shutting down MCP servers...")

        for name, server_info in self.servers.items():
            try:
                session = server_info["session"]
                stdio_context = server_info["stdio_context"]

                # Fecha sessão
                await session.__aexit__(None, None, None)

                # Fecha stdio context
                await stdio_context.__aexit__(None, None, None)

                logger.info(f"Closed MCP server: {name}")
            except Exception as e:
                logger.error(f"Error closing server {name}: {e}")

        self.servers.clear()
        self.tools.clear()
        self.server_for_tool.clear()
        self.is_initialized = False
        logger.info("MCP shutdown complete")


# Singleton global
mcp_orchestrator = MCPOrchestrator()
