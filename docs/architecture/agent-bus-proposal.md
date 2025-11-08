# 🚌 Proposta: Arquitetura de Barramento de Agentes

## 📋 Status: AGUARDANDO APROVAÇÃO

**Criado em:** 2025-11-03
**Autor:** Claude + Paulo Teixeira

---

## 🎯 Objetivo

Criar uma arquitetura que permita **múltiplos agentes especializados** (vendas, suporte, onboarding, etc.) cada um com:
- ✅ Prompt próprio carregado dinamicamente
- ✅ Conjunto específico de tools disponíveis
- ✅ Configuração de comportamento independente
- ✅ Carregamento via barramento/registro central

## 🏗️ Arquitetura Atual vs Proposta

### Atual (Monolítico)
```
WhatsApp → /chat → chat.py → prompts.py (ÚNICO) → anthropic_driver
                                ↓
                           mcp_orchestrator (TODAS as tools)
```

**Limitações:**
- ❌ Um único prompt hardcoded para todos os casos de uso
- ❌ Todas as tools sempre disponíveis (mesmo que não relevantes)
- ❌ Impossível ter comportamentos diferentes por contexto
- ❌ Prompt gigante e difícil de manter

### Proposta (Barramento de Agentes)
```
WhatsApp → /chat → AgentBus.get_agent(agent_type) → Agent Instance
                        ↓                                    ↓
                   AgentRegistry                    - prompt específico
                   (configs/)                       - tools filtradas
                                                     - modelo específico
                                                     - temperature
```

**Vantagens:**
- ✅ Múltiplos agentes especializados
- ✅ Configuração em arquivos separados (fácil manutenção)
- ✅ Tools contextualizadas por agente
- ✅ Hot-reload de configurações
- ✅ A/B testing de prompts
- ✅ Escala melhor (diferentes modelos/custos por agente)

---

## 📂 Estrutura de Arquivos Proposta

```
alabia-conductor/
├── packages/
│   └── agents/                          # NOVO: Core do sistema de agentes
│       ├── __init__.py
│       ├── base_agent.py                # Classe base Agent
│       ├── agent_bus.py                 # Barramento de agentes
│       ├── agent_registry.py            # Registro/carregamento
│       └── agent_config.py              # Schema de configuração
│
├── configs/                             # NOVO: Configurações dos agentes
│   └── agents/
│       ├── sales.yaml                   # Agente de vendas (atual)
│       ├── support.yaml                 # Agente de suporte
│       ├── onboarding.yaml              # Agente de onboarding
│       └── schemas/
│           └── agent_config_schema.json # JSON Schema para validação
│
├── prompts/                             # NOVO: Prompts separados
│   ├── sales/
│   │   ├── system.md                    # Prompt principal (atual ALABIA_SYSTEM_PROMPT)
│   │   ├── tools/
│   │   │   ├── create_event.md          # Instruções de uso da tool
│   │   │   ├── create_lead.md
│   │   │   └── check_availability.md
│   │   └── examples/
│   │       └── conversations.yaml       # Exemplos de conversas
│   │
│   ├── support/
│   │   ├── system.md
│   │   └── tools/
│   │       ├── file_search.md           # Suporte usa RAG
│   │       └── list_events.md           # Consultar agendas
│   │
│   └── onboarding/
│       ├── system.md
│       └── tools/
│           └── file_search.md
│
└── apps/orchestrator/
    └── routes/
        └── chat.py                      # MODIFICADO: Usa AgentBus
```

---

## 🔧 Componentes Principais

### 1. **Agent Config (YAML)**

```yaml
# configs/agents/sales.yaml
agent_id: "alabia-sales-v1"
name: "Alabia Sales Agent"
description: "Agente comercial para agendamento de reuniões"

# LLM Configuration
llm:
  model: "claude-sonnet-4"
  temperature: 0.7
  max_tokens: 4000

# Prompt Configuration
prompts:
  system_prompt_path: "prompts/sales/system.md"
  tool_instructions_path: "prompts/sales/tools"
  examples_path: "prompts/sales/examples/conversations.yaml"

# Tools whitelist (apenas estas estarão disponíveis)
tools:
  allowed:
    - "create_event"
    - "check_availability"
    - "list_events"
    - "cancel_event"
    - "create_lead"
    - "file_search"  # Para buscar info sobre Alabia

  # Ordem de prioridade (para o prompt)
  priority:
    - "check_availability"  # Sempre verificar primeiro
    - "create_event"        # Depois agendar
    - "create_lead"         # Depois criar lead

# Behavior flags
behavior:
  auto_create_lead: true           # Criar lead automaticamente
  require_email: true              # Sempre pedir email
  business_hours_only: true        # Restringir a horário comercial
  max_conversation_turns: 10       # Limite de turnos
  timezone: "America/Sao_Paulo"

# Context requirements
context:
  required_fields:
    - "phone"  # user_id sempre presente
  optional_fields:
    - "name"
    - "email"

# Fallback behavior
fallback:
  agent_id: "alabia-support-v1"  # Se não conseguir agendar
  trigger_keywords:
    - "problema"
    - "erro"
    - "suporte"
```

### 2. **Agent Base Class**

```python
# packages/agents/base_agent.py

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class AgentConfig:
    """Configuração de um agente"""
    agent_id: str
    name: str
    model: str
    temperature: float
    system_prompt: str
    allowed_tools: List[str]
    behavior: Dict[str, Any]
    context_requirements: Dict[str, List[str]]

class BaseAgent:
    """Classe base para todos os agentes"""

    def __init__(self, config: AgentConfig, mcp_orchestrator):
        self.config = config
        self.mcp = mcp_orchestrator

    def build_system_prompt(self, context: Dict[str, Any]) -> str:
        """
        Constrói o prompt do sistema com contexto dinâmico
        - Carrega prompt base do arquivo .md
        - Injeta informações temporais
        - Injeta contexto do usuário
        - Adiciona instruções das tools permitidas
        """
        pass

    def get_available_tools(self) -> List[Dict]:
        """
        Retorna apenas as tools permitidas para este agente
        Filtra do mcp_orchestrator.tools
        """
        pass

    async def chat(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: List[Dict]
    ) -> Dict[str, Any]:
        """
        Executa conversa com o agente
        - Valida contexto requerido
        - Constrói prompt
        - Chama LLM driver
        - Retorna resposta
        """
        pass

    def validate_context(self, context: Dict) -> bool:
        """Valida se contexto tem campos requeridos"""
        pass
```

### 3. **Agent Registry**

```python
# packages/agents/agent_registry.py

class AgentRegistry:
    """Registro de agentes disponíveis"""

    def __init__(self, configs_path: Path):
        self.configs_path = configs_path
        self.agents = {}
        self._load_all_agents()

    def _load_all_agents(self):
        """Carrega todos os .yaml da pasta configs/agents/"""
        for yaml_file in self.configs_path.glob("*.yaml"):
            agent = self._load_agent_from_yaml(yaml_file)
            self.agents[agent.config.agent_id] = agent

    def _load_agent_from_yaml(self, yaml_path: Path) -> BaseAgent:
        """
        1. Parse YAML
        2. Carrega system prompt do .md
        3. Carrega tool instructions
        4. Cria AgentConfig
        5. Instancia BaseAgent
        """
        pass

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Retorna agente pelo ID"""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[str]:
        """Lista todos os agent_ids disponíveis"""
        return list(self.agents.keys())

    def reload_agent(self, agent_id: str):
        """Hot-reload de um agente (útil para desenvolvimento)"""
        pass
```

### 4. **Agent Bus**

```python
# packages/agents/agent_bus.py

class AgentBus:
    """Barramento para roteamento de mensagens para agentes"""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.routing_rules = {}

    def route_message(
        self,
        message: str,
        context: Dict[str, Any],
        agent_id: Optional[str] = None
    ) -> BaseAgent:
        """
        Decide qual agente usar baseado em:
        1. agent_id explícito (se fornecido)
        2. Palavras-chave da mensagem
        3. Contexto (ex: se já tem lead aberto)
        4. Default: sales agent
        """

        # Explícito
        if agent_id:
            return self.registry.get_agent(agent_id)

        # Por keywords
        if any(kw in message.lower() for kw in ["problema", "erro", "suporte"]):
            return self.registry.get_agent("alabia-support-v1")

        if any(kw in message.lower() for kw in ["como usar", "tutorial", "começar"]):
            return self.registry.get_agent("alabia-onboarding-v1")

        # Default: sales
        return self.registry.get_agent("alabia-sales-v1")

    async def process_message(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: List[Dict],
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        1. Roteia para agente correto
        2. Executa chat
        3. Retorna resposta + metadata
        """
        agent = self.route_message(message, context, agent_id)

        response = await agent.chat(message, context, conversation_history)

        return {
            "response": response,
            "agent_used": agent.config.agent_id,
            "agent_name": agent.config.name
        }
```

### 5. **Chat Endpoint Modificado**

```python
# apps/orchestrator/routes/chat.py

from packages.agents.agent_bus import AgentBus
from packages.agents.agent_registry import AgentRegistry

# Global (inicializado no startup)
agent_registry = AgentRegistry(Path("configs/agents"))
agent_bus = AgentBus(agent_registry)

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Endpoint modificado para usar AgentBus
    """

    # Constrói histórico
    conversation_history = []
    if request.context and request.context.previous_messages:
        conversation_history = _build_conversation_history(
            request.context.previous_messages
        )

    # Contexto
    context = {
        "phone": request.user_id,
        "name": request.context.name if request.context else None,
        "email": request.context.email if request.context else None,
    }

    # Roteia para agente e processa
    result = await agent_bus.process_message(
        message=request.message,
        context=context,
        conversation_history=conversation_history,
        agent_id=request.agent_id  # Opcional: forçar agente específico
    )

    return {
        "response": result["response"],
        "agent_used": result["agent_used"],  # Metadata
        "timestamp": datetime.now().isoformat()
    }
```

---

## 📝 Exemplo: Prompt Separado

```markdown
<!-- prompts/sales/system.md -->

Você é um assistente de atendimento comercial da Alabia, empresa brasileira especializada em Inteligência Artificial e Robótica.

## 🎯 COMPORTAMENTO CORE

### 1. SEJA PROATIVO COM AS TOOLS
- SEMPRE consulte as tools ANTES de fazer perguntas ao cliente
- NÃO peça informações que você pode descobrir usando tools
- NÃO invente dados - use APENAS informações reais das tools

<!-- Resto do prompt... -->
```

```markdown
<!-- prompts/sales/tools/create_event.md -->

### create_event
**Quando usar:** Após confirmar disponibilidade e obter email
**Como usar:** `create_event(title="...", start_datetime="...", attendee_email="...")`

**⭐ IMPORTANTE:** O create_event SEMPRE cria um link do Google Meet automaticamente!
- Quando confirmar o agendamento, SEMPRE mencione o link do Meet

**Parâmetros:**
- title: "Reunião - [Nome do Cliente]"
- start_datetime: formato ISO com timezone -03:00
- duration_minutes: padrão 60min
- attendee_email: email do cliente (OBRIGATÓRIO)

<!-- Exemplos... -->
```

---

## 🎯 Casos de Uso

### Caso 1: Agente de Vendas (Atual)
```yaml
agent_id: "alabia-sales-v1"
tools: [create_event, check_availability, create_lead, list_events, cancel_event]
behavior:
  auto_create_lead: true
  business_hours_only: true
```

### Caso 2: Agente de Suporte
```yaml
agent_id: "alabia-support-v1"
tools: [file_search, list_events]  # Sem criar eventos!
behavior:
  auto_create_lead: false
  escalate_to_human: true  # Se não resolver
```

### Caso 3: Agente de Onboarding
```yaml
agent_id: "alabia-onboarding-v1"
tools: [file_search]  # Apenas consulta docs
behavior:
  tutorial_mode: true
  step_by_step: true
```

### Caso 4: A/B Testing
```yaml
# configs/agents/sales-v2-experimental.yaml
agent_id: "alabia-sales-v2"
prompts:
  system_prompt_path: "prompts/sales-v2/system.md"  # Variação do prompt
llm:
  temperature: 0.5  # Mais conservador
```

---

## 🔄 Fluxo de Mensagem Completo

```
1. WhatsApp → POST /chat
              {
                "user_id": "5511999999999",
                "message": "Quero agendar",
                "agent_id": null  # Opcional
              }

2. AgentBus.route_message()
   → Analisa "quero agendar"
   → Retorna SalesAgent

3. SalesAgent.build_system_prompt()
   → Carrega prompts/sales/system.md
   → Injeta data/hora atual
   → Injeta contexto do usuário
   → Adiciona instruções das 6 tools permitidas

4. SalesAgent.get_available_tools()
   → Filtra apenas: create_event, check_availability, etc.
   → Remove tools de outros agentes

5. SalesAgent.chat()
   → Chama anthropic_driver com prompt construído
   → Driver executa tools via mcp_orchestrator
   → Retorna resposta

6. Response
   {
     "response": "Claro! Quando você prefere?",
     "agent_used": "alabia-sales-v1",
     "timestamp": "2025-11-03T14:30:00"
   }
```

---

## 📊 Comparação: Antes vs Depois

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Prompts** | 1 arquivo Python hardcoded | N arquivos .md separados |
| **Tools** | Todas sempre disponíveis | Filtradas por agente |
| **Manutenção** | Editar código Python | Editar YAML + Markdown |
| **Especialização** | Impossível | 1 agente por caso de uso |
| **A/B Testing** | Impossível | Criar config alternativa |
| **Hot-reload** | Restart servidor | Reload config |
| **Escalabilidade** | Prompt gigante | Prompts modulares |
| **Custo** | Sempre Sonnet-4 | Modelos diferentes por agente |

---

## 🚀 Plano de Implementação (SE APROVADO)

### Fase 1: Core (1-2 dias)
- [ ] Criar `packages/agents/base_agent.py`
- [ ] Criar `packages/agents/agent_registry.py`
- [ ] Criar `packages/agents/agent_bus.py`
- [ ] Criar schema YAML de configuração

### Fase 2: Migração (1 dia)
- [ ] Mover prompt atual para `prompts/sales/system.md`
- [ ] Criar `configs/agents/sales.yaml`
- [ ] Modificar `chat.py` para usar AgentBus
- [ ] Testar paridade com versão atual

### Fase 3: Novos Agentes (1-2 dias)
- [ ] Criar agente de suporte
- [ ] Criar agente de onboarding
- [ ] Criar roteamento automático por keywords

### Fase 4: Features Avançadas (1 dia)
- [ ] Hot-reload de configurações
- [ ] Admin endpoint `/agents` (listar, recarregar)
- [ ] Logging de qual agente foi usado
- [ ] Métricas por agente

---

## ⚠️ Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Breaking changes | Alto | Manter compatibilidade no /chat |
| Complexidade adicional | Médio | Boa documentação + exemplos |
| Performance (carregamento) | Baixo | Cache de prompts carregados |
| Sincronização de configs | Médio | Validação via JSON Schema |

---

## 🤔 Decisões Pendentes

1. **Formato de prompt:** Markdown ou YAML com templates?
2. **Roteamento:** Automático por keywords ou sempre explícito?
3. **Fallback:** Quando um agente não consegue resolver, passa para outro?
4. **Versionamento:** Como versionar prompts? (`sales-v1`, `sales-v2`...)
5. **Storage:** YAML local ou futuramente buscar de DB/API?

---

## 📋 Próximos Passos

1. ✅ **Revisar esta proposta**
   - Arquitetura faz sentido?
   - Formato YAML + MD é adequado?
   - Casos de uso cobrem necessidades?

2. ⏳ **Aprovar ou ajustar**
   - Quais mudanças sugerir?
   - Prioridades diferentes?

3. ⏳ **Implementar (se aprovado)**
   - Seguir plano de 4 fases
   - Manter testes funcionando

---

## 💬 Feedback

**O que você acha?**

- A arquitetura proposta resolve o problema?
- YAML + Markdown é uma boa escolha?
- Prefere começar simples ou já com tudo?
- Outros requisitos que não foram cobertos?

**Aguardando seu feedback para prosseguir! 🚀**
