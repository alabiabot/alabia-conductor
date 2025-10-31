"""
Anthropic Claude Driver
Wrapper para SDK da Anthropic com suporte a MCP tools
"""
import logging
from typing import List, Dict, Any, Optional
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from apps.orchestrator.settings import settings

logger = logging.getLogger(__name__)


class AnthropicDriver:
    """
    Driver para Anthropic Claude com suporte a function calling via MCP
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Inicializa o driver

        Args:
            api_key: API key da Anthropic (usa settings se None)
            model: Nome do modelo (usa settings se None)
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.anthropic_model
        self.client = AsyncAnthropic(api_key=self.api_key)

        logger.info(f"Anthropic driver initialized with model: {self.model}")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Message:
        """
        Envia mensagem para Claude

        Args:
            messages: Lista de mensagens no formato [{"role": "user", "content": "..."}]
            system: System prompt
            tools: Lista de tools disponíveis (formato MCP/Anthropic)
            max_tokens: Máximo de tokens na resposta
            temperature: Temperatura (0-1)

        Returns:
            Message object da Anthropic
        """
        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or settings.anthropic_max_tokens,
            "temperature": temperature or settings.anthropic_temperature,
        }

        if system:
            params["system"] = system

        if tools:
            params["tools"] = tools

        try:
            response = await self.client.messages.create(**params)
            logger.debug(f"Claude response: {response.model_dump_json(indent=2)}")
            return response

        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}", exc_info=True)
            raise

    async def chat_with_tools(
        self,
        user_message: str,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[callable] = None,
        max_iterations: Optional[int] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Chat com loop automático de function calling

        Args:
            user_message: Mensagem do usuário
            system: System prompt
            tools: Lista de tools disponíveis
            tool_executor: Função async que executa tools
            max_iterations: Máximo de iterações (evita loop infinito)
            conversation_history: Histórico de conversa anterior

        Returns:
            {
                "response": str,
                "actions": List[ToolAction],
                "final_message": Message
            }
        """
        max_iter = max_iterations or settings.max_tool_iterations
        messages = conversation_history or []
        messages.append({"role": "user", "content": user_message})

        actions = []
        iterations = 0

        while iterations < max_iter:
            iterations += 1
            logger.info(f"Chat iteration {iterations}/{max_iter}")

            # Chama Claude
            response = await self.chat(
                messages=messages,
                system=system,
                tools=tools
            )

            # Se não pediu tool, terminou
            if response.stop_reason == "end_turn":
                text_response = self._extract_text(response)
                logger.info(f"Chat completed in {iterations} iterations")
                return {
                    "response": text_response,
                    "actions": actions,
                    "final_message": response
                }

            # Se pediu tools
            if response.stop_reason == "tool_use":
                # Adiciona resposta do Claude às mensagens
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Executa cada tool solicitada
                tool_results = []
                for content_block in response.content:
                    if isinstance(content_block, ToolUseBlock):
                        logger.info(f"Executing tool: {content_block.name}")

                        # Executa tool
                        if tool_executor:
                            try:
                                result = await tool_executor(
                                    tool_name=content_block.name,
                                    tool_input=content_block.input
                                )

                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": content_block.id,
                                    "content": str(result)
                                })

                                actions.append({
                                    "tool": content_block.name,
                                    "status": "success",
                                    "result": result
                                })

                            except Exception as e:
                                logger.error(f"Tool execution error: {e}", exc_info=True)

                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": content_block.id,
                                    "is_error": True,
                                    "content": f"Error: {str(e)}"
                                })

                                actions.append({
                                    "tool": content_block.name,
                                    "status": "error",
                                    "result": None,
                                    "error": str(e)
                                })

                # Adiciona resultados das tools
                if tool_results:
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                # Continua o loop

        # Se chegou ao limite de iterações
        logger.warning(f"Max iterations ({max_iter}) reached")
        text_response = self._extract_text(response) or "Desculpe, não consegui processar sua solicitação."

        return {
            "response": text_response,
            "actions": actions,
            "final_message": response
        }

    def _extract_text(self, message: Message) -> str:
        """Extrai texto da resposta do Claude"""
        text_blocks = [
            block.text
            for block in message.content
            if isinstance(block, TextBlock)
        ]
        return "\n".join(text_blocks) if text_blocks else ""

    @staticmethod
    def format_tool_for_anthropic(mcp_tool: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converte tool MCP para formato Anthropic

        Args:
            mcp_tool: Tool no formato MCP

        Returns:
            Tool no formato Anthropic
        """
        return {
            "name": mcp_tool["name"],
            "description": mcp_tool.get("description", ""),
            "input_schema": mcp_tool.get("inputSchema", {
                "type": "object",
                "properties": {},
                "required": []
            })
        }
