# Ogamex Bot - Walkthrough Completo (Arquitetura Modular)

## 🏗️ Visão Geral da Arquitetura

O bot foi completamente modularizado para manutenibilidade e extensibilidade:

```
raidex-ninjabot/
├── bot.py                           # Orquestrador principal
├── web_app.py                       # Servidor Flask para interface web
├── config.json                      # Configurações do usuário
├── modules/
│   ├── __init__.py
│   ├── config.py                    # Carregamento de configurações
│   ├── cooldown_manager.py          # Rastreamento de cooldown (asteroides específicos)
│   ├── asteroid_finder.py           # Lógica de busca de asteroides
│   ├── fleet_dispatcher.py          # Lógica de envio de frotas
│   ├── empire_manager.py            # Gerenciamento do império
│   └── stealth.py                   # Evasões anti-detecção
├── templates/                       # Templates HTML
│   ├── base.html
│   ├── asteroid_miner.html
│   └── empire.html
├── asteroid_cooldowns.json          # Dados de cooldown (auto-gerado)
├── empire_data.json                 # Dados do império (auto-gerado)
└── user_data/                       # Perfil persistente do navegador
```

## ✨ Funcionalidades Principais

### 1. **Design Modular**
- Separação clara de responsabilidades
- Fácil adicionar novas funcionalidades (espionagem, ataques, etc.)
- Cada módulo tem uma única responsabilidade
- Todas as configurações centralizadas em `config.json`

### 2. **Rastreamento Específico de Asteroides** ⭐
**Problema Resolvido**: Intervalos sobrepostos causando tentativas duplicadas de mineração.

**Exemplo**:
- Intervalo 1: `[3:5:17]` → `[3:25:17]` (encontra asteroide no sistema 20)
- Intervalo 2: `[3:15:17]` → `[3:35:17]` (encontraria o mesmo asteroide em 20!)

**Solução**: Cooldown salva **coordenadas exatas** `3:20:17` ao invés de intervalos.

```json
{
  "3:20:17": 1732074000.123,
  "3:433:17": 1732074500.456
}
```

### 3. **Ciclos de Espera Inteligentes** ⭐
- Busca asteroides continuamente quando disponíveis
- **Espera Randomizada**: Aguarda 25-40 minutos (configurável) quando nenhum asteroide é encontrado para imitar comportamento humano
- **Auto-Navegação**: Força retorno à visualização Galaxy antes de cada busca para garantir estado correto

### 4. **Detecção Robusta de Botões** ⭐
- Aguarda o botão "Find asteroids" aparecer (manipula carregamento dinâmico)
- Tenta novamente se o carregamento da página for lento
- Previne falsos negativos onde o bot pensou que não havia asteroides

### 5. **Automação de Envio de Frotas**
- Seleciona grupo de frotas (configurável em config.json)
- Navega automaticamente por todos os passos do wizard de frotas
- Retorna à visualização da galáxia para continuar buscando

### 6. **Gerenciamento de Império** 🆕
- Coleta dados de todos os planetas/luas
- Extrai recursos atuais, capacidade de armazenamento, produção
- Lista edifícios, construções em andamento
- Mostra frotas disponíveis por planeta
- Atualização manual via botão "Crawl Empire"

### 7. **Interface Web Moderna** 🆕
- **Painel de Controle**: Inicie/pare o bot com um clique
- **Logs em Tempo Real**: Acompanhe todas as ações do bot
- **Visualização de Cooldowns**: Veja asteroides em cooldown e tempo restante
- **Dashboard do Império**: Visualize todos os planetas, recursos e frotas
- **Configuração Dinâmica**: Ajuste configurações via API REST

### 8. **Modo Stealth** �
- **Evasões de WebDriver**: Remove propriedades detectáveis
- **User-Agent Realista**: Simula navegador real
- **Perfil Persistente**: Mantém sessão de login
- **Argumentos Otimizados**: Desabilita recursos de automação

## 🎯 Resultados dos Testes

### Execução Bem-Sucedida:
```
📍 Navegando para a página da galáxia...
✓ Página da galáxia carregada

🔍 Aguardando o botão 'Find asteroids'...
✓ Botão 'Find' de asteroides detectado! Clicando...
📊 Encontradas 4 faixa(s) de asteroides para verificar

🔍 Verificando intervalo [3:129:17] → [3:149:17]
  → Verificando sistema 129...
  → Asteroide 3:130:17 está em cooldown. 0.9h restantes.
  → Verificando sistema 131...

🎯 ASTEROIDE ENCONTRADO: [3:135:17]
  ⏱  Timer do asteroide: 45 minutos
  📏 Distância: 112 sistemas
  ✅ Tempo suficiente! Enviando frota...
  
⏳ Selecionando grupo de frotas: 300 MM
✓ Grupo de frotas selecionado: 300 MM
✅ Frota enviada com sucesso!
✓ Adicionado 3:135:17 ao cooldown por 1h
```

## ⚙️ Configuração

Todas as configurações em `config.json`:

```json
{
    "HEADLESS_MODE": false,
    "FLEET_GROUP_NAME": "300 MM",
    "COOLDOWN_HOURS": 1,
    "SEARCH_DELAY_MIN": 0.3,
    "SEARCH_DELAY_MAX": 1,
    "NO_ASTEROID_WAIT_MIN": 45,
    "NO_ASTEROID_WAIT_MAX": 60,
    "FLEET_FAIL_WAIT_MINUTES": 50
}
```

**Parâmetros**:
- `HEADLESS_MODE`: Executar navegador invisível (false = visível)
- `FLEET_GROUP_NAME`: Nome do grupo de frotas a usar
- `COOLDOWN_HOURS`: Horas de cooldown para asteroides
- `SEARCH_DELAY_MIN/MAX`: Delay entre verificações de sistemas (segundos)
- `NO_ASTEROID_WAIT_MIN/MAX`: Espera quando sem asteroides (minutos)
- `FLEET_FAIL_WAIT_MINUTES`: Espera após falha de envio (minutos)

📖 **Para configurações avançadas**, consulte [`docs/CONFIGURATION.md`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/docs/CONFIGURATION.md)

## 📊 Como Funciona

### Fluxo Principal:
1. **Inicialização**: Carrega sessão do navegador, dados de cooldown
2. **Busca**: Clica no botão "Find asteroids"
3. **Parsing**: Extrai intervalos de asteroides do modal
4. **Filtro**: Pula asteroides em cooldown
5. **Varredura**: Verifica cada sistema sequencialmente
6. **Envio**: Envia frota quando asteroide é encontrado
7. **Salvar**: Armazena coordenadas específicas em cooldown
8. **Repetir**: Continua ou aguarda se nenhum asteroide

### Lógica de Cooldown:
```python
# Antes de verificar sistema
if cooldown_mgr.is_in_cooldown(galaxy=3, system=20, position=17):
    skip  # Não verifica este asteroide

# Após envio bem-sucedido
cooldown_mgr.add_to_cooldown(galaxy=3, system=20, position=17)
```

### Validação de Tempo de Viagem:
```python
# Calcula distância do planeta base
distance = abs(asteroid_system - BASE_SYSTEM)

# Obtém tempo mínimo necessário baseado na distância
required_time = get_required_travel_time(distance)

# Valida se o asteroide tem tempo suficiente
if asteroid_timer >= required_time:
    dispatch_fleet()  # Enviar!
else:
    skip  # Muito longe, não dá tempo
```

## 🗂️ Responsabilidades dos Módulos

### [`bot.py`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/bot.py)
- Orquestrador principal
- Inicializa módulos
- Roda loop principal
- Trata erros
- Sistema de logging com queue
- Threading para não bloquear servidor web

### [`modules/config.py`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/modules/config.py)
- Carregamento de `config.json`
- Validação de configurações
- Mapeamento de grupos de frotas
- Valores padrão

### [`modules/cooldown_manager.py`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/modules/cooldown_manager.py)
- Carrega/salva cooldowns em JSON
- Verifica se asteroide específico está em cooldown
- Limpeza automática de cooldowns expirados
- Retorna contagem de cooldowns ativos

### [`modules/asteroid_finder.py`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/modules/asteroid_finder.py)
- Detecta botão "Find asteroids"
- Faz parsing de intervalos do modal
- Busca sistemas sequencialmente
- Valida tempo de viagem vs distância
- Clica no asteroide quando encontrado

### [`modules/fleet_dispatcher.py`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/modules/fleet_dispatcher.py)
- Seleciona grupo de frotas
- Navega pelos passos do wizard
- Envia frota
- Retorna à galáxia

### [`modules/empire_manager.py`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/modules/empire_manager.py) 🆕
- Busca dados do império
- Faz parsing da página Empire
- Extrai informações de planetas
- Salva em `empire_data.json`
- Fornece dados via API

### [`modules/stealth.py`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/modules/stealth.py) 🆕
- Argumentos do Chrome para evasão
- Injeta JavaScript para remover detectores
- Emula permissões de navegador real
- Oculta propriedades de automação

### [`web_app.py`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/web_app.py) 🆕
- Servidor Flask
- Renderiza templates HTML
- API REST para controle do bot
- Endpoints para logs, cooldowns, configuração
- Endpoints para dados do império

## 🚀 Executando o Bot

### Modo 1: Linha de Comando (Legado)
```bash
python bot.py
```

### Modo 2: Interface Web (Recomendado)
```bash
python web_app.py
```
Depois acesse: `http://localhost:5000`

### Saída:
- ✅ Saída rica com emojis no console
- ✅ Indicadores de progresso claros
- ✅ Logging passo a passo
- ✅ Mensagens de erro com contexto
- ✅ Logs em tempo real na interface web

## 🌐 Interface Web

### Aba "Asteroid Miner"
- **Controles**: Botões Start/Stop
- **Logs**: Últimas 100 linhas com timestamps
- **Cooldowns**: Lista de asteroides em cooldown com tempo restante
- **Auto-refresh**: Atualização automática a cada 2 segundos

### Aba "Empire"
- **Dashboard de Planetas**: Todos os planetas/luas
- **Recursos**: Metal, Crystal, Deuterium, Energy
- **Armazenamento**: Capacidade atual vs máxima
- **Produção**: Recursos por hora
- **Edifícios**: Níveis e construções em andamento
- **Frotas**: Naves disponíveis por planeta
- **Defesas**: Defesas instaladas
- **Botão Crawl**: Atualização manual dos dados

## 📈 Benefícios do Design Modular

### ✅ **Fácil de Estender**
Quer adicionar espionagem? Crie `modules/spy.py`:
```python
from modules import config, cooldown_manager

class Spy:
    async def spy_on_player(self, page, target):
        # Implementação aqui
        pass
```

Depois importe em `bot.py`:
```python
from modules.spy import Spy
spy = Spy()
```

### ✅ **Fácil de Testar**
Cada módulo pode ser testado independentemente:
```python
# Testa gerenciador de cooldown
mgr = CooldownManager("test.json", 1)
mgr.add_to_cooldown(3, 100, 17)
assert mgr.is_in_cooldown(3, 100, 17) == True
```

### ✅ **Fácil de Manter**
- Bug no envio de frotas? Edite apenas `fleet_dispatcher.py`
- Quer mudar estratégia de busca? Edite apenas `asteroid_finder.py`
- Precisa de lógica de cooldown diferente? Edite apenas `cooldown_manager.py`

## 📡 API REST

Veja [`docs/API.md`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/docs/API.md) para documentação completa.

### Endpoints Principais:
- `GET /api/status` - Status do bot e logs
- `POST /api/start` - Iniciar bot
- `POST /api/stop` - Parar bot
- `GET /api/cooldowns` - Obter cooldowns
- `GET /api/config` - Obter configuração
- `POST /api/config` - Atualizar configuração
- `GET /api/empire/data` - Dados do império
- `POST /api/empire/crawl` - Disparar crawl do império

## 🎯 Critérios de Sucesso

- [x] Arquitetura modular com 7 módulos limpos
- [x] Coordenadas específicas de asteroides rastreadas (não intervalos)
- [x] Previne mineração duplicada do mesmo asteroide
- [x] Espera inteligente de 45-60 minutos quando sem asteroides
- [x] Envio de frotas totalmente automatizado
- [x] Todas as configurações centralizadas
- [x] Fácil de estender com novas funcionalidades
- [x] Verificado funcionando com descoberta real de asteroides
- [x] Interface web moderna com controle em tempo real
- [x] Gerenciamento completo do império
- [x] Modo stealth para evitar detecção

## 🔮 Extensões Futuras (Fácil de Adicionar!)

Com o design modular, você pode facilmente adicionar:
- **Módulo de Espionagem**: Auto-espionar alvos
- **Módulo de Ataque**: Auto-atacar alvos fracos
- **Módulo de Transporte**: Auto-transportar recursos
- **Módulo de Defesa**: Auto-fleetsave antes de ataques
- **Módulo de Mercado**: Auto-negociar no marketplace
- **Notificações**: Telegram/Discord quando asteroide encontrado
- **Dashboard Analytics**: Gráficos de recursos minerados ao longo do tempo

## 📚 Documentação Adicional

- [`README.md`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/README.md) - Documentação principal em português
- [`CONFIGURATION.md`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/docs/CONFIGURATION.md) - Guia completo de configuração
- [`API.md`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/docs/API.md) - Documentação da API REST
- [`MODULES.md`](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/docs/MODULES.md) - Documentação técnica dos módulos

---

**Desenvolvido com ❤️ para automação inteligente no Ogamex**

