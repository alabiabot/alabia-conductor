# 🚌 Arquitetura de Barramento de Agentes - REFINADA

## 📋 Status: APROVADO PARA IMPLEMENTAÇÃO

**Versão:** 2.0 (Refinada com feedback)
**Criado em:** 2025-11-03
**Aprovado em:** 2025-11-03

---

## 🎯 Decisões Arquiteturais

### ✅ Aprovado
- **Arquitetura modular** com BaseAgent + AgentRegistry + AgentBus
- **YAML + Markdown** para configuração
- **Começar simples**: 1 agente (sales) migrado com paridade completa
- **Fallback** para comportamento antigo se algo quebrar
- **Logging estruturado** desde o início

### 📋 Decisões Tomadas

| Questão | Decisão | Razão |
|---------|---------|-------|
| **Formato de prompt** | Markdown com `{{placeholders}}` | Legível, versionável no git |
| **Template engine** | Jinja2 | Explícito, poderoso, bem conhecido |
| **Roteamento inicial** | Explícito via parâmetro `agent_id` | Simples, previsível, testável |
| **Roteamento futuro** | Keywords com logging do "porquê" | Transparência para debug |
| **Fallback** | Sim, para "general agent" ou legado | Não quebra /chat existente |
| **Versionamento** | `sales-v1.yaml`, `sales-v2.yaml` | Git-friendly, A/B testing fácil |
| **Storage** | YAML local (git), backend plugável | Agora simples, futuro flexível |
| **Validação** | JSON Schema obrigatório | Evita configs inválidos |

---

## 🏗️ Arquitetura Final

```
┌─────────────────────────────────────────────────────────────┐
│                       WhatsApp/API                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │   POST /chat          │
          │   - message           │
          │   - context           │
          │   - agent_id (opt)    │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │     AgentBus          │
          │  - route()            │
          │  - process()          │
          │  - log()              │
          └───────────┬───────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
    ┌────────┐  ┌────────┐  ┌────────┐
    │ Sales  │  │Support │  │General │
    │ Agent  │  │ Agent  │  │ Agent  │
    │ (v1)   │  │ (v1)   │  │(fallback)
    └────┬───┘  └────┬───┘  └────┬───┘
         │           │            │
         └───────────┼────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │   MCP Orchestrator   │
          │  - RAG               │
          │  - Calendar          │
          │  - Pipedrive         │
          └──────────────────────┘
```

---

## 📝 Contratos (Interfaces)

### 1. BaseAgent (Interface Clara)

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AgentResponse:
    """Resposta padronizada de um agente"""
    content: str                    # Texto da resposta
    agent_id: str                   # Qual agente respondeu
    model_used: str                 # claude-sonnet-4, etc.
    tools_called: List[str]         # ['check_availability', 'create_event']
    latency_ms: int                 # Tempo de processamento
    tokens_used: int                # Total de tokens
    estimated_cost_usd: float       # Custo estimado
    metadata: Dict[str, Any]        # Dados extras

@dataclass
class AgentConfig:
    """Configuração carregada do YAML"""
    agent_id: str                   # "alabia-sales-v1"
    name: str                       # "Alabia Sales Agent"
    version: str                    # "v1"
    model: str                      # "claude-sonnet-4"
    temperature: float              # 0.7
    max_tokens: int                 # 4000
    system_prompt_template: str     # Conteúdo do .md com {{vars}}
    allowed_tools: List[str]        # ['create_event', 'check_availability']
    tool_priority: List[str]        # Ordem de prioridade
    behavior: Dict[str, Any]        # Flags de comportamento
    routing: Dict[str, Any]         # Keywords, strategy
    fallback_agent_id: Optional[str] # Se falhar

class BaseAgent(ABC):
    """Contrato que todo agente deve implementar"""

    def __init__(self, config: AgentConfig, mcp_orchestrator):
        self.config = config
        self.mcp = mcp_orchestrator
        self.metrics = AgentMetrics(config.agent_id)

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do agente"""
        pass

    @property
    @abstractmethod
    def supported_tools(self) -> List[str]:
        """Tools que este agente pode usar"""
        pass

    @abstractmethod
    async def infer(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: List[Dict]
    ) -> AgentResponse:
        """
        Método principal: processa mensagem e retorna resposta
        """
        pass

    def can_handle(self, message: str, context: Dict[str, Any]) -> bool:
        """
        Opcional: retorna True se este agente pode lidar com a mensagem
        Usado para roteamento automático futuro
        """
        return False  # Override em subclasses

    def _render_prompt(self, context: Dict[str, Any]) -> str:
        """
        Renderiza template Jinja2 com contexto
        """
        from jinja2 import Template
        template = Template(self.config.system_prompt_template)
        return template.render(**context)

    def _get_available_tools(self) -> List[Dict]:
        """
        Filtra tools do MCP orchestrator
        """
        all_tools = self.mcp.get_tools()
        return [
            t for t in all_tools
            if t['name'] in self.config.allowed_tools
        ]

    async def _log_interaction(
        self,
        message: str,
        response: AgentResponse,
        context: Dict[str, Any]
    ):
        """
        Log estruturado de cada interação
        """
        logger.info(
            "agent_interaction",
            extra={
                "agent_id": self.config.agent_id,
                "agent_version": self.config.version,
                "model": response.model_used,
                "user_id": context.get("phone"),
                "message_length": len(message),
                "response_length": len(response.content),
                "tools_called": response.tools_called,
                "latency_ms": response.latency_ms,
                "tokens": response.tokens_used,
                "cost_usd": response.estimated_cost_usd,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        self.metrics.record(response)
```

### 2. AgentRegistry (Descoberta + Validação)

```python
import yaml
import json
from pathlib import Path
from jsonschema import validate, ValidationError

class AgentRegistry:
    """Carrega, valida e gerencia agentes"""

    def __init__(
        self,
        configs_path: Path,
        prompts_path: Path,
        schema_path: Path
    ):
        self.configs_path = configs_path
        self.prompts_path = prompts_path
        self.schema = self._load_schema(schema_path)
        self.agents: Dict[str, BaseAgent] = {}
        self._load_all_agents()

    def _load_schema(self, schema_path: Path) -> dict:
        """Carrega JSON Schema de validação"""
        with open(schema_path) as f:
            return json.load(f)

    def _validate_config(self, config: dict):
        """Valida config contra schema"""
        try:
            validate(instance=config, schema=self.schema)
        except ValidationError as e:
            raise ValueError(f"Invalid agent config: {e.message}")

    def _load_all_agents(self):
        """Carrega todos os YAMLs da pasta configs/agents/"""
        for yaml_file in self.configs_path.glob("*.yaml"):
            try:
                agent = self._load_agent_from_yaml(yaml_file)
                self.agents[agent.config.agent_id] = agent
                logger.info(f"Loaded agent: {agent.config.agent_id}")
            except Exception as e:
                logger.error(f"Failed to load {yaml_file}: {e}")
                # Não falha a aplicação toda se 1 agente tiver erro

    def _load_agent_from_yaml(self, yaml_path: Path) -> BaseAgent:
        """
        1. Parse YAML
        2. Valida com JSON Schema
        3. Carrega system prompt do .md
        4. Renderiza com Jinja2
        5. Cria AgentConfig
        6. Instancia SalesAgent/SupportAgent/etc
        """
        with open(yaml_path) as f:
            config_dict = yaml.safe_load(f)

        # Valida
        self._validate_config(config_dict)

        # Carrega prompt
        prompt_path = self.prompts_path / config_dict['prompts']['system_prompt_path']
        with open(prompt_path) as f:
            system_prompt_template = f.read()

        # Cria config
        agent_config = AgentConfig(
            agent_id=config_dict['agent_id'],
            name=config_dict['name'],
            version=config_dict.get('version', 'v1'),
            model=config_dict['llm']['model'],
            temperature=config_dict['llm']['temperature'],
            max_tokens=config_dict['llm'].get('max_tokens', 4000),
            system_prompt_template=system_prompt_template,
            allowed_tools=config_dict['tools']['allowed'],
            tool_priority=config_dict['tools'].get('priority', []),
            behavior=config_dict.get('behavior', {}),
            routing=config_dict.get('routing', {}),
            fallback_agent_id=config_dict.get('fallback', {}).get('agent_id')
        )

        # Instancia agente específico
        agent_type = config_dict.get('type', 'sales')
        if agent_type == 'sales':
            return SalesAgent(agent_config, mcp_orchestrator)
        elif agent_type == 'support':
            return SupportAgent(agent_config, mcp_orchestrator)
        else:
            return GeneralAgent(agent_config, mcp_orchestrator)

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Retorna agente pelo ID"""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        """Lista metadados de todos os agentes"""
        return [
            {
                "agent_id": agent.config.agent_id,
                "name": agent.config.name,
                "version": agent.config.version,
                "tools": agent.config.allowed_tools,
                "model": agent.config.model
            }
            for agent in self.agents.values()
        ]

    def reload_agent(self, agent_id: str):
        """Hot-reload de um agente específico"""
        # Encontra arquivo YAML original
        yaml_file = self.configs_path / f"{agent_id}.yaml"
        if yaml_file.exists():
            agent = self._load_agent_from_yaml(yaml_file)
            self.agents[agent_id] = agent
            logger.info(f"Reloaded agent: {agent_id}")
        else:
            raise FileNotFoundError(f"Config not found: {yaml_file}")
```

### 3. AgentBus (Orquestração + Logging)

```python
class AgentBus:
    """Barramento para roteamento e orquestração"""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.routing_strategy = ExplicitRoutingStrategy()  # Começa simples

    async def process_message(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: List[Dict],
        agent_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> AgentResponse:
        """
        Pipeline completo:
        1. Enriquece contexto
        2. Roteia para agente
        3. Executa inferência
        4. Loga interação
        5. Retorna resposta
        """
        request_id = request_id or str(uuid.uuid4())
        start_time = datetime.utcnow()

        # 1. Enriquece contexto
        enriched_context = self._enrich_context(context)

        # 2. Roteia
        agent, routing_reason = self._route_to_agent(
            message, enriched_context, agent_id
        )

        # 3. Log de roteamento
        logger.info(
            "agent_routing",
            extra={
                "request_id": request_id,
                "agent_selected": agent.config.agent_id,
                "routing_reason": routing_reason,
                "explicit_agent": agent_id is not None
            }
        )

        try:
            # 4. Executa
            response = await agent.infer(
                message, enriched_context, conversation_history
            )

            # 5. Log de resposta
            await self._log_response(
                request_id, message, response, enriched_context, start_time
            )

            return response

        except Exception as e:
            # 6. Fallback se agente falhar
            logger.error(f"Agent {agent.config.agent_id} failed: {e}")
            if agent.config.fallback_agent_id:
                fallback_agent = self.registry.get_agent(
                    agent.config.fallback_agent_id
                )
                if fallback_agent:
                    logger.info(f"Falling back to {fallback_agent.config.agent_id}")
                    return await fallback_agent.infer(
                        message, enriched_context, conversation_history
                    )
            raise

    def _route_to_agent(
        self,
        message: str,
        context: Dict[str, Any],
        explicit_agent_id: Optional[str]
    ) -> Tuple[BaseAgent, str]:
        """
        Estratégia de roteamento:
        1. Explícito via parâmetro (agora)
        2. Keywords (futuro)
        3. ML (muito futuro)
        """

        # Explícito sempre tem prioridade
        if explicit_agent_id:
            agent = self.registry.get_agent(explicit_agent_id)
            if agent:
                return agent, "explicit_parameter"

        # Strategy pattern (facilita trocar no futuro)
        agent, reason = self.routing_strategy.route(
            message, context, self.registry
        )

        return agent, reason

    def _enrich_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adiciona informações ao contexto:
        - Data/hora atual
        - Timezone
        - Features habilitadas
        - Tenant info (futuro multi-tenant)
        """
        tz_br = timezone(timedelta(hours=-3))
        now = datetime.now(tz_br)

        return {
            **context,
            "current_datetime": now.isoformat(),
            "current_date": now.strftime("%Y-%m-%d"),
            "current_time": now.strftime("%H:%M"),
            "day_of_week": now.strftime("%A"),
            "is_weekend": now.weekday() >= 5,
            "is_business_hours": 8 <= now.hour < 18 and now.weekday() < 5,
            "timezone": "America/Sao_Paulo"
        }

    async def _log_response(
        self,
        request_id: str,
        message: str,
        response: AgentResponse,
        context: Dict[str, Any],
        start_time: datetime
    ):
        """Log estruturado completo"""
        total_latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            "agent_response",
            extra={
                "request_id": request_id,
                "agent_id": response.agent_id,
                "model": response.model_used,
                "user_id": context.get("phone"),
                "input_length": len(message),
                "output_length": len(response.content),
                "tools_called": response.tools_called,
                "tools_count": len(response.tools_called),
                "agent_latency_ms": response.latency_ms,
                "total_latency_ms": total_latency,
                "tokens": response.tokens_used,
                "cost_usd": response.estimated_cost_usd,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

class ExplicitRoutingStrategy:
    """Estratégia inicial: sempre usa sales agent"""

    def route(
        self,
        message: str,
        context: Dict[str, Any],
        registry: AgentRegistry
    ) -> Tuple[BaseAgent, str]:
        """Retorna sales agent por padrão"""
        sales_agent = registry.get_agent("alabia-sales-v1")
        if sales_agent:
            return sales_agent, "default_sales"

        # Se não tem sales, pega qualquer um
        agents = list(registry.agents.values())
        if agents:
            return agents[0], "fallback_first_available"

        raise ValueError("No agents available in registry")
```

---

## 📂 Estrutura de Arquivos (Refinada)

```
alabia-conductor/
├── packages/
│   └── agents/
│       ├── __init__.py
│       ├── base_agent.py              # BaseAgent (interface)
│       ├── agent_registry.py          # AgentRegistry
│       ├── agent_bus.py               # AgentBus
│       ├── agent_metrics.py           # Métricas por agente
│       ├── routing_strategies.py      # Estratégias de roteamento
│       └── implementations/
│           ├── sales_agent.py         # SalesAgent(BaseAgent)
│           ├── support_agent.py       # SupportAgent(BaseAgent)
│           └── general_agent.py       # GeneralAgent(BaseAgent)
│
├── configs/
│   └── agents/
│       ├── sales-v1.yaml              # Agente de vendas
│       ├── general-v1.yaml            # Agente genérico (fallback)
│       └── schemas/
│           └── agent_config.schema.json  # JSON Schema
│
├── prompts/
│   ├── sales/
│   │   └── system.md                  # Prompt migrado de prompts.py
│   └── general/
│       └── system.md                  # Prompt genérico
│
└── apps/orchestrator/
    └── routes/
        └── chat.py                    # Usa AgentBus
```

---

## 📋 Plano de Implementação - FASE 1+2 (Foco: Paridade)

### Objetivo: Migrar agente sales atual sem quebrar nada

### Fase 1: Infra Core (Dia 1)

#### 1.1 Criar estrutura base
```bash
mkdir -p packages/agents/implementations
mkdir -p configs/agents/schemas
mkdir -p prompts/sales
touch packages/agents/{__init__,base_agent,agent_registry,agent_bus,agent_metrics}.py
```

#### 1.2 Implementar BaseAgent (interface)
- [ ] Criar dataclasses: `AgentResponse`, `AgentConfig`
- [ ] Definir `BaseAgent` com métodos abstratos
- [ ] Implementar `_render_prompt()` com Jinja2
- [ ] Implementar `_get_available_tools()`
- [ ] Implementar `_log_interaction()`

#### 1.3 Implementar AgentMetrics
```python
class AgentMetrics:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.interactions = 0
        self.total_latency = 0
        self.total_cost = 0

    def record(self, response: AgentResponse):
        self.interactions += 1
        self.total_latency += response.latency_ms
        self.total_cost += response.estimated_cost_usd

    def get_stats(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "interactions": self.interactions,
            "avg_latency_ms": self.total_latency / max(self.interactions, 1),
            "total_cost_usd": self.total_cost
        }
```

#### 1.4 Implementar AgentRegistry
- [ ] Método `_load_schema()`
- [ ] Método `_validate_config()`
- [ ] Método `_load_agent_from_yaml()`
- [ ] Método `get_agent()`
- [ ] Método `list_agents()`

#### 1.5 Implementar AgentBus
- [ ] Método `process_message()`
- [ ] Método `_route_to_agent()` (simples: sempre sales)
- [ ] Método `_enrich_context()`
- [ ] Método `_log_response()`
- [ ] Classe `ExplicitRoutingStrategy`

### Fase 2: Migração Sales Agent (Dia 2)

#### 2.1 Criar JSON Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["agent_id", "name", "llm", "prompts", "tools"],
  "properties": {
    "agent_id": {"type": "string", "pattern": "^[a-z0-9-]+$"},
    "name": {"type": "string"},
    "version": {"type": "string", "default": "v1"},
    "llm": {
      "type": "object",
      "required": ["model", "temperature"],
      "properties": {
        "model": {"type": "string"},
        "temperature": {"type": "number", "minimum": 0, "maximum": 2},
        "max_tokens": {"type": "integer", "default": 4000}
      }
    },
    "prompts": {
      "type": "object",
      "required": ["system_prompt_path"],
      "properties": {
        "system_prompt_path": {"type": "string"}
      }
    },
    "tools": {
      "type": "object",
      "required": ["allowed"],
      "properties": {
        "allowed": {
          "type": "array",
          "items": {"type": "string"}
        },
        "priority": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    }
  }
}
```

#### 2.2 Migrar prompt atual
- [ ] Copiar `packages/llm/prompts.py` → `prompts/sales/system.md`
- [ ] Converter para Markdown puro
- [ ] Adicionar placeholders Jinja2:
  - `{{current_datetime}}`
  - `{{user_name}}`
  - `{{user_email}}`
  - `{{user_phone}}`

#### 2.3 Criar sales-v1.yaml
```yaml
agent_id: "alabia-sales-v1"
name: "Alabia Sales Agent"
version: "v1"
type: "sales"

llm:
  model: "claude-sonnet-4"
  temperature: 0.7
  max_tokens: 4000

prompts:
  system_prompt_path: "sales/system.md"

tools:
  allowed:
    - "create_event"
    - "check_availability"
    - "list_events"
    - "cancel_event"
    - "create_lead"
    - "file_search"
  priority:
    - "check_availability"
    - "create_event"
    - "create_lead"

behavior:
  auto_create_lead: true
  require_email: true
  business_hours_only: true

fallback:
  agent_id: "alabia-general-v1"
```

#### 2.4 Implementar SalesAgent
```python
class SalesAgent(BaseAgent):
    """Agente de vendas - migração do comportamento atual"""

    @property
    def name(self) -> str:
        return "Alabia Sales Agent"

    @property
    def supported_tools(self) -> List[str]:
        return self.config.allowed_tools

    async def infer(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: List[Dict]
    ) -> AgentResponse:
        start_time = datetime.utcnow()

        # Renderiza prompt com contexto
        system_prompt = self._render_prompt(context)

        # Busca tools disponíveis
        tools = self._get_available_tools()

        # Chama driver Anthropic (mesmo código atual)
        from packages.llm.anthropic_driver import chat_with_tools

        response_text, tools_called, tokens = await chat_with_tools(
            user_message=message,
            system_prompt=system_prompt,
            tools=tools,
            mcp_client=self.mcp,
            conversation_history=conversation_history,
            model=self.config.model,
            temperature=self.config.temperature
        )

        # Monta resposta
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        cost = self._estimate_cost(tokens, self.config.model)

        agent_response = AgentResponse(
            content=response_text,
            agent_id=self.config.agent_id,
            model_used=self.config.model,
            tools_called=tools_called,
            latency_ms=int(latency),
            tokens_used=tokens,
            estimated_cost_usd=cost,
            metadata={}
        )

        # Log
        await self._log_interaction(message, agent_response, context)

        return agent_response

    def _estimate_cost(self, tokens: int, model: str) -> float:
        """Estimativa de custo por modelo"""
        pricing = {
            "claude-sonnet-4": 0.003 / 1000,  # $3 per 1M tokens
            "claude-haiku": 0.00025 / 1000     # $0.25 per 1M tokens
        }
        return tokens * pricing.get(model, 0.003 / 1000)
```

#### 2.5 Criar GeneralAgent (fallback)
```python
class GeneralAgent(BaseAgent):
    """Agente genérico - fallback quando sales falha"""

    @property
    def name(self) -> str:
        return "Alabia General Agent"

    @property
    def supported_tools(self) -> List[str]:
        return ["file_search"]  # Só consulta docs

    async def infer(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: List[Dict]
    ) -> AgentResponse:
        # Implementação similar ao SalesAgent
        # mas com prompt genérico e sem auto-create-lead
        pass
```

#### 2.6 Modificar chat.py
```python
# apps/orchestrator/routes/chat.py

from packages.agents.agent_registry import AgentRegistry
from packages.agents.agent_bus import AgentBus

# Inicializar no startup
agent_registry = None
agent_bus = None

@app.on_event("startup")
async def startup_event():
    global agent_registry, agent_bus

    # Carrega agentes
    configs_path = Path("configs/agents")
    prompts_path = Path("prompts")
    schema_path = Path("configs/agents/schemas/agent_config.schema.json")

    agent_registry = AgentRegistry(configs_path, prompts_path, schema_path)
    agent_bus = AgentBus(agent_registry)

    logger.info(f"Loaded {len(agent_registry.agents)} agents")

@router.post("/chat")
async def chat(request: ChatRequest):
    """Endpoint modificado para usar AgentBus"""

    # Constrói histórico (mesmo código atual)
    conversation_history = []
    if request.context and request.context.previous_messages:
        conversation_history = _build_conversation_history(
            request.context.previous_messages
        )

    # Contexto
    context = {
        "phone": request.user_id,
        "user_name": request.context.name if request.context else None,
        "user_email": request.context.email if request.context else None,
    }

    # Processa via AgentBus
    response = await agent_bus.process_message(
        message=request.message,
        context=context,
        conversation_history=conversation_history,
        agent_id=getattr(request, 'agent_id', None)  # Novo campo opcional
    )

    return {
        "response": response.content,
        "agent_id": response.agent_id,
        "model": response.model_used,
        "tools_called": response.tools_called,
        "latency_ms": response.latency_ms,
        "timestamp": datetime.now().isoformat()
    }
```

### Fase 2.7: Testes de Paridade

```python
# tests/test_agent_migration.py

async def test_sales_agent_paridade():
    """
    Verifica que SalesAgent tem mesmo comportamento que código antigo
    """

    # Mesmos inputs
    message = "Quero agendar amanhã 14h"
    context = {
        "phone": "5511999999999",
        "user_name": "Paulo",
        "user_email": "paulo@test.com"
    }

    # Resposta do agent novo
    response = await agent_bus.process_message(message, context, [])

    # Validações
    assert "check_availability" in response.tools_called
    assert "create_event" in response.tools_called
    assert "create_lead" in response.tools_called
    assert response.agent_id == "alabia-sales-v1"
    assert len(response.content) > 0
```

---

## 📊 Logging Estruturado (Obrigatório desde Fase 1)

### Formato de Log

```json
{
  "event": "agent_response",
  "request_id": "uuid-1234",
  "timestamp": "2025-11-03T14:30:00Z",
  "agent_id": "alabia-sales-v1",
  "agent_version": "v1",
  "model": "claude-sonnet-4",
  "user_id": "5511999999999",
  "input_length": 23,
  "output_length": 145,
  "tools_called": ["check_availability", "create_event", "create_lead"],
  "tools_count": 3,
  "agent_latency_ms": 1234,
  "total_latency_ms": 1350,
  "tokens": 850,
  "cost_usd": 0.00255,
  "routing_reason": "explicit_parameter"
}
```

### Configuração (python-json-logger)

```python
import logging
from pythonjsonlogger import jsonlogger

handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(name)s %(levelname)s %(message)s'
)
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

---

## ✅ Checklist de Implementação

### Fase 1: Core (Dia 1)
- [ ] Criar estrutura de pastas
- [ ] Implementar `BaseAgent` (interface clara)
- [ ] Implementar `AgentMetrics`
- [ ] Implementar `AgentRegistry` (com validação)
- [ ] Implementar `AgentBus` (com logging)
- [ ] Configurar logging estruturado (JSON)
- [ ] Testes unitários do core

### Fase 2: Migração (Dia 2)
- [ ] Criar JSON Schema de validação
- [ ] Migrar prompt para `prompts/sales/system.md`
- [ ] Criar `configs/agents/sales-v1.yaml`
- [ ] Criar `configs/agents/general-v1.yaml`
- [ ] Implementar `SalesAgent`
- [ ] Implementar `GeneralAgent`
- [ ] Modificar `chat.py` para usar `AgentBus`
- [ ] Adicionar flag de fallback para código antigo
- [ ] Testes de paridade (mesmo comportamento)
- [ ] Deploy em staging
- [ ] Validação manual (10 conversas)
- [ ] Deploy em produção com monitoramento

---

## 🎯 Critérios de Sucesso (Fase 1+2)

✅ **Funcional:**
- [ ] SalesAgent responde identicamente ao código antigo
- [ ] Todas as tools funcionam (create_event, create_lead, etc.)
- [ ] Fallback para GeneralAgent funciona se SalesAgent falhar
- [ ] Nenhuma regressão detectada em 100 conversas de teste

✅ **Técnico:**
- [ ] JSON Schema valida todos os YAMLs
- [ ] Logs estruturados em JSON
- [ ] Métricas coletadas (latência, custo, tokens)
- [ ] Coverage > 80% nos testes

✅ **Operacional:**
- [ ] Documentação completa de como adicionar novo agente
- [ ] Runbook de troubleshooting
- [ ] Alertas configurados (latência, erro, custo)

---

## 📚 Próximas Fases (Após Fase 1+2)

### Fase 3: Novos Agentes (Futuro)
- [ ] Criar SupportAgent
- [ ] Criar OnboardingAgent
- [ ] Implementar roteamento por keywords
- [ ] A/B testing: sales-v1 vs sales-v2

### Fase 4: Features Avançadas (Futuro)
- [ ] Hot-reload de configs
- [ ] Admin endpoint `/agents` (listar, recarregar)
- [ ] Dashboard de métricas por agente
- [ ] Roteamento via ML (classificador)

---

## 🚨 Riscos Mitigados

| Risco | Mitigação Implementada |
|-------|------------------------|
| Drift de comportamento | JSON Schema + code review obrigatório |
| Tools demais por agente | Whitelist explícita em YAML |
| Debug difícil | Logging estruturado + request_id |
| Config inválido | Validação no load + testes |
| Breaking change | Fallback para código antigo via flag |
| Perda de performance | Métricas de latência desde Fase 1 |

---

## 📖 Documentação Adicional

Após implementação, criar:
- [ ] `docs/agents/adding-new-agent.md` (tutorial)
- [ ] `docs/agents/prompt-guidelines.md` (boas práticas)
- [ ] `docs/agents/troubleshooting.md` (runbook)
- [ ] `docs/agents/metrics.md` (dashboards)

---

**Status:** ✅ PRONTO PARA COMEÇAR FASE 1

**Próximo passo:** Começar implementação do BaseAgent
