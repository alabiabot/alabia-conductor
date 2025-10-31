"""
Chat endpoint - Integração com WhatsApp backend
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from packages.llm.anthropic_driver import AnthropicDriver
from apps.orchestrator.mcp_client import mcp_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()

# Inicializa driver (singleton)
anthropic_driver = AnthropicDriver()


# Schemas
class ChatContext(BaseModel):
    """Contexto adicional da conversa"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    previous_messages: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Request do endpoint /chat"""
    user_id: str = Field(..., description="ID único do usuário (ex: número WhatsApp)")
    message: str = Field(..., description="Mensagem do usuário")
    context: Optional[ChatContext] = Field(default=None, description="Contexto adicional")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "5511999999999",
                    "message": "Quero agendar uma reunião",
                    "context": {
                        "name": "João Silva",
                        "email": "joao@empresa.com"
                    }
                }
            ]
        }
    }


class ToolAction(BaseModel):
    """Ação executada por uma tool"""
    tool: str
    status: str  # "success" | "error"
    result: Any
    error: Optional[str] = None


class ChatResponse(BaseModel):
    """Response do endpoint /chat"""
    response: str = Field(..., description="Resposta para o usuário")
    actions: List[ToolAction] = Field(default_factory=list, description="Tools executadas")
    needs_followup: bool = Field(default=False, description="Aguarda mais interação")
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Endpoint principal de chat

    Recebe mensagem do backend WhatsApp, processa com Claude + MCP tools,
    e retorna resposta + ações executadas.
    """
    logger.info(f"Chat request from user {request.user_id}: {request.message[:50]}...")

    try:
        # 1. Inicializa MCP orchestrator (se necessário)
        if not mcp_orchestrator.is_initialized:
            await mcp_orchestrator.initialize()

        # 2. Get available tools
        mcp_tools = await mcp_orchestrator.get_tools()
        anthropic_tools = [
            AnthropicDriver.format_tool_for_anthropic(tool)
            for tool in mcp_tools
        ]

        # 3. Build system prompt
        system_prompt = _build_system_prompt(request.context)

        # 4. Process with Claude + MCP loop
        result = await anthropic_driver.chat_with_tools(
            user_message=request.message,
            system=system_prompt,
            tools=anthropic_tools,
            tool_executor=mcp_orchestrator.execute_tool
        )

        # 5. Format response
        return ChatResponse(
            response=result["response"],
            actions=[
                ToolAction(**action) for action in result["actions"]
            ],
            needs_followup=_check_needs_followup(result["response"]),
            metadata={
                "user_id": request.user_id,
                "tools_used": [a["tool"] for a in result["actions"]],
                "iterations": len(result["actions"]) + 1
            }
        )

    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )


def _build_system_prompt(context: Optional[ChatContext]) -> str:
    """Constrói system prompt para Claude"""

    base_prompt = """Você é o assistente inteligente da Alabia, uma plataforma de atendimento com IA.

Seu papel é ajudar clientes via WhatsApp com:
- Informações sobre planos e preços
- Agendamento de reuniões comerciais
- Dúvidas sobre serviços e funcionalidades
- Suporte técnico básico

Você tem acesso às seguintes ferramentas:
- file_search: Busca em documentação interna (preços, FAQ, etc)
- create_event: Cria eventos no Google Calendar
- check_availability: Verifica horários disponíveis
- web_search: Busca informações na internet (use apenas se necessário)

Diretrizes:
- Seja cordial, profissional e prestativo
- Use linguagem natural e amigável
- Quando agendar reuniões, sempre confirme com o cliente antes de criar
- Para dúvidas sobre preços/funcionalidades, use file_search primeiro
- Sempre pergunte o email do cliente antes de agendar reunião
- Seja conciso nas respostas (WhatsApp)

Tom de voz: Profissional mas descontraído, típico brasileiro"""

    # Adiciona contexto do usuário se disponível
    if context:
        user_info = []
        if context.name:
            user_info.append(f"Nome: {context.name}")
        if context.email:
            user_info.append(f"Email: {context.email}")
        if context.phone:
            user_info.append(f"Telefone: {context.phone}")

        if user_info:
            base_prompt += f"\n\nInformações do cliente:\n" + "\n".join(user_info)

    return base_prompt


def _check_needs_followup(response: str) -> bool:
    """Verifica se a resposta indica que precisa de mais interação"""
    followup_indicators = [
        "?",  # Pergunta
        "qual",
        "quando",
        "prefere",
        "gostaria",
        "confirme",
        "confirma"
    ]
    response_lower = response.lower()
    return any(indicator in response_lower for indicator in followup_indicators)


@router.get("/chat/health")
async def chat_health():
    """Health check do módulo de chat"""

    # Check MCP status
    mcp_status = "initialized" if mcp_orchestrator.is_initialized else "not_initialized"
    tools_count = len(mcp_orchestrator.tools) if mcp_orchestrator.is_initialized else 0

    return {
        "status": "healthy",
        "module": "chat",
        "anthropic": {
            "model": anthropic_driver.model,
            "status": "ready"
        },
        "mcp": {
            "status": mcp_status,
            "tools_count": tools_count,
            "tools": list(mcp_orchestrator.tools.keys()) if mcp_orchestrator.is_initialized else []
        }
    }
