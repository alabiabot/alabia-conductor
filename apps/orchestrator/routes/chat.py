"""
Chat endpoint - Integração com WhatsApp backend
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from packages.llm.anthropic_driver import AnthropicDriver
from packages.llm.prompts import ALABIA_SYSTEM_PROMPT
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

        # 4. Build conversation history from context
        conversation_history = []
        if request.context and request.context.previous_messages:
            conversation_history = _build_conversation_history(request.context.previous_messages)

        # 5. Process with Claude + MCP loop
        result = await anthropic_driver.chat_with_tools(
            user_message=request.message,
            system=system_prompt,
            tools=anthropic_tools,
            tool_executor=mcp_orchestrator.execute_tool,
            conversation_history=conversation_history
        )

        # 6. Format response
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


def _build_conversation_history(previous_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Converte previous_messages para formato Anthropic

    Expected format:
    [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
        ...
    ]
    """
    history = []
    for msg in previous_messages:
        role = msg.get("role", "user")
        content = msg.get("content", msg.get("text", ""))

        if role and content:
            history.append({"role": role, "content": content})

    return history


def _build_system_prompt(context: Optional[ChatContext]) -> str:
    """Constrói system prompt para Claude"""
    from datetime import datetime, timezone, timedelta

    # Usa o prompt otimizado do arquivo prompts.py
    base_prompt = ALABIA_SYSTEM_PROMPT

    # Adiciona data/hora atual (timezone Brasil = UTC-3)
    tz_br = timezone(timedelta(hours=-3))
    now = datetime.now(tz_br)

    base_prompt += f"\n\n## 📅 CONTEXTO TEMPORAL\n"
    base_prompt += f"- **Data/Hora Atual:** {now.strftime('%Y-%m-%d %H:%M')} (Brasil)\n"
    base_prompt += f"- **Dia da Semana:** {now.strftime('%A')}\n"
    base_prompt += f"- **É fim de semana:** {'Sim' if now.weekday() >= 5 else 'Não'}\n"
    base_prompt += f"\n**Use esta informação para calcular 'hoje', 'amanhã', etc.**\n"

    # Se for fora do horário comercial, avise
    if now.hour < 8 or now.hour >= 18 or now.weekday() >= 5:
        base_prompt += f"\n⚠️ **IMPORTANTE:** Estamos fora do horário comercial (Seg-Sex 8h-18h).\n"
        base_prompt += f"Ofereça agendar para próximo dia útil.\n"

    # Adiciona contexto do usuário se disponível
    if context:
        user_info = []
        if context.name:
            user_info.append(f"**Nome: {context.name}**")
        if context.email:
            user_info.append(f"**Email: {context.email}** ← USE ESTE EMAIL quando o cliente disser 'o mesmo'")
        if context.phone:
            user_info.append(f"**Telefone/WhatsApp: {context.phone}** ← USE no person_phone do create_lead")

        if user_info:
            base_prompt += f"\n\n## 👤 INFORMAÇÕES DO CLIENTE\n" + "\n".join(f"- {info}" for info in user_info)
            base_prompt += "\n\n**⚠️ IMPORTANTE:**"
            base_prompt += "\n- Quando o cliente disser 'o mesmo email', use o email acima"
            base_prompt += "\n- SEMPRE use o telefone acima no campo person_phone do create_lead"
            base_prompt += "\n- NUNCA use telefone como email!"

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
