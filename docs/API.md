# 🌐 Documentação da API REST - Raidex-NinjaBot

Documentação completa da API REST da interface web do bot, incluindo todos os endpoints, parâmetros, respostas e exemplos de uso.

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Endpoints de Interface](#-endpoints-de-interface)
- [Endpoints de Status](#-endpoints-de-status)
- [Endpoints de Controle do Bot](#-endpoints-de-controle-do-bot)
- [Endpoints de Configuração](#-endpoints-de-configuração)
- [Endpoints do Império](#-endpoints-do-império)
- [Exemplos de Integração](#-exemplos-de-integração)

## 🔍 Visão Geral

### Base URL
```
http://localhost:5000
```

### Formato de Resposta
Todas as respostas da API são em formato JSON.

### Headers Comuns
```
Content-Type: application/json
```

## 🖼️ Endpoints de Interface

### GET `/`
Renderiza a interface principal do minerador de asteroides.

**Resposta**: HTML da página `asteroid_miner.html`

**Exemplo**:
```bash
curl http://localhost:5000/
```

---

### GET `/empire`
Renderiza a interface de gerenciamento do império.

**Resposta**: HTML da página `empire.html`

**Exemplo**:
```bash
curl http://localhost:5000/empire
```

## 📊 Endpoints de Status

### GET `/api/status`
Retorna o status atual do bot e logs recentes.

**Resposta**:
```json
{
    "running": true,
    "logs": [
        "[01:23:45] Bot started",
        "[01:23:46] 🚀 Launching browser...",
        "[01:23:50] ✓ Galaxy page loaded",
        "[01:23:55] 🔍 Searching for asteroids...",
        "[01:24:00] 🎯 ASTEROID FOUND: [3:135:17]"
    ]
}
```

**Campos**:
- `running` (boolean): Se o bot está atualmente em execução
- `logs` (array): Últimas 100 linhas de log com timestamps

**Exemplo**:
```bash
curl http://localhost:5000/api/status
```

**Uso**: A interface web chama este endpoint a cada 2 segundos para atualizar os logs em tempo real.

---

### GET `/api/cooldowns`
Retorna todos os asteroides atualmente em cooldown.

**Resposta**:
```json
{
    "3:135:17": 1732228800.123,
    "3:220:17": 1732229100.456,
    "3:433:17": 1732229400.789
}
```

**Estrutura**:
- **Chave**: Coordenadas do asteroide `"galaxy:system:position"`
- **Valor**: Timestamp Unix (segundos) de quando o cooldown expira

**Exemplo**:
```bash
curl http://localhost:5000/api/cooldowns
```

**Conversão de Timestamp**:
```javascript
// JavaScript
const expiryTime = new Date(timestamp * 1000);
const now = new Date();
const remainingMinutes = (expiryTime - now) / 1000 / 60;
```

```python
# Python
import time
from datetime import datetime

expiry_timestamp = 1732228800.123
expiry_time = datetime.fromtimestamp(expiry_timestamp)
remaining_seconds = expiry_timestamp - time.time()
remaining_minutes = remaining_seconds / 60
```

## 🎮 Endpoints de Controle do Bot

### POST `/api/start`
Inicia o bot de mineração de asteroides.

**Request**: Nenhum corpo necessário

**Resposta**:
```json
{
    "status": "started"
}
```

**Ou se já estiver rodando**:
```json
{
    "status": "already running"
}
```

**Exemplo**:
```bash
curl -X POST http://localhost:5000/api/start
```

**JavaScript**:
```javascript
fetch('http://localhost:5000/api/start', {
    method: 'POST'
})
.then(response => response.json())
.then(data => console.log(data));
```

---

### POST `/api/stop`
Para o bot de mineração de asteroides.

**Request**: Nenhum corpo necessário

**Resposta**:
```json
{
    "status": "stopping"
}
```

**Ou se não estiver rodando**:
```json
{
    "status": "not running"
}
```

**Exemplo**:
```bash
curl -X POST http://localhost:5000/api/stop
```

> [!NOTE]
> O bot não para imediatamente. Ele termina a operação atual (ex: enviar frota) antes de parar completamente.

## ⚙️ Endpoints de Configuração

### GET `/api/config`
Retorna a configuração atual do bot.

**Resposta**:
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

**Exemplo**:
```bash
curl http://localhost:5000/api/config
```

---

### POST `/api/config`
Atualiza a configuração do bot.

**Request Body** (JSON):
```json
{
    "HEADLESS_MODE": false,
    "FLEET_GROUP_NAME": "320 MM",
    "COOLDOWN_HOURS": 1.5,
    "SEARCH_DELAY_MIN": 0.5,
    "SEARCH_DELAY_MAX": 1.5,
    "NO_ASTEROID_WAIT_MIN": 30,
    "NO_ASTEROID_WAIT_MAX": 45,
    "FLEET_FAIL_WAIT_MINUTES": 30
}
```

**Resposta (Sucesso)**:
```json
{
    "status": "saved"
}
```

**Resposta (Erro)**:
```json
{
    "error": "Invalid config format"
}
```

**Exemplo**:
```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "FLEET_GROUP_NAME": "320 MM",
    "COOLDOWN_HOURS": 1.5
  }'
```

**JavaScript**:
```javascript
const newConfig = {
    "FLEET_GROUP_NAME": "320 MM",
    "COOLDOWN_HOURS": 1.5,
    "NO_ASTEROID_WAIT_MIN": 30,
    "NO_ASTEROID_WAIT_MAX": 45
};

fetch('http://localhost:5000/api/config', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(newConfig)
})
.then(response => response.json())
.then(data => console.log(data));
```

> [!IMPORTANT]
> As mudanças de configuração são aplicadas no próximo ciclo de busca do bot. Algumas mudanças (como `HEADLESS_MODE`) podem requerer reiniciar o bot.

## 🏛️ Endpoints do Império

### GET `/api/empire/data`
Retorna os dados do império (planetas, recursos, frotas).

**Resposta**:
```json
{
    "planets": [
        {
            "id": "6e3d63fb-afb6-44d4-8440-4768b52cbc3f",
            "name": "Planeta Principal",
            "coords": "[3:247:8]",
            "resources": {
                "metal": 1250000,
                "crystal": 850000,
                "deuterium": 450000,
                "energy": 5000
            },
            "storage": {
                "metal": 2000000,
                "crystal": 1500000,
                "deuterium": 1000000
            },
            "production": {
                "metal_hour": 12500,
                "crystal_hour": 8500,
                "deuterium_hour": 4200
            },
            "buildings": {
                "Metal Mine": { "level": 25, "in_progress": false },
                "Crystal Mine": { "level": 22, "in_progress": false },
                "Deuterium Synthesizer": { "level": 18, "in_progress": true, "time_remaining": "2h 35m" }
            },
            "ships": {
                "Small Cargo": 450,
                "Large Cargo": 120,
                "Light Fighter": 200,
                "Heavy Fighter": 50,
                "Cruiser": 25
            },
            "defenses": {
                "Rocket Launcher": 100,
                "Light Laser": 50,
                "Heavy Laser": 25
            }
        }
    ],
    "last_update": "2025-11-22T01:15:30"
}
```

**Campos Principais**:
- `planets` (array): Lista de todos os planetas/luas
  - `id`: UUID do planeta
  - `name`: Nome do planeta
  - `coords`: Coordenadas no formato `[galaxy:system:position]`
  - `resources`: Recursos atuais (metal, crystal, deuterium, energy)
  - `storage`: Capacidade de armazenamento
  - `production`: Produção por hora
  - `buildings`: Edifícios e status de construção
  - `ships`: Frotas disponíveis
  - `defenses`: Defesas instaladas
- `last_update`: Timestamp da última atualização

**Exemplo**:
```bash
curl http://localhost:5000/api/empire/data
```

---

### POST `/api/empire/crawl`
Dispara uma atualização manual dos dados do império.

**Request**: Nenhum corpo necessário

**Resposta (Sucesso)**:
```json
{
    "status": "success",
    "message": "Crawl scheduled"
}
```

**Resposta (Erro - Bot não está rodando)**:
```json
{
    "status": "error",
    "message": "Bot is not running"
}
```

**Exemplo**:
```bash
curl -X POST http://localhost:5000/api/empire/crawl
```

**Como funciona**:
1. O endpoint dispara uma tarefa assíncrona no loop do bot
2. O bot navega para a página Empire
3. Extrai todos os dados de planetas, recursos, frotas, etc.
4. Salva os dados em `empire_data.json`
5. Os dados ficam disponíveis via `/api/empire/data`

> [!NOTE]
> O crawl leva alguns segundos para completar. Use polling em `/api/empire/data` para obter os dados atualizados.

## 💻 Exemplos de Integração

### Dashboard Customizado em JavaScript

```javascript
class RaidexAPI {
    constructor(baseUrl = 'http://localhost:5000') {
        this.baseUrl = baseUrl;
    }

    async getStatus() {
        const response = await fetch(`${this.baseUrl}/api/status`);
        return await response.json();
    }

    async startBot() {
        const response = await fetch(`${this.baseUrl}/api/start`, {
            method: 'POST'
        });
        return await response.json();
    }

    async stopBot() {
        const response = await fetch(`${this.baseUrl}/api/stop`, {
            method: 'POST'
        });
        return await response.json();
    }

    async getCooldowns() {
        const response = await fetch(`${this.baseUrl}/api/cooldowns`);
        return await response.json();
    }

    async getConfig() {
        const response = await fetch(`${this.baseUrl}/api/config`);
        return await response.json();
    }

    async updateConfig(config) {
        const response = await fetch(`${this.baseUrl}/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        return await response.json();
    }

    async getEmpireData() {
        const response = await fetch(`${this.baseUrl}/api/empire/data`);
        return await response.json();
    }

    async crawlEmpire() {
        const response = await fetch(`${this.baseUrl}/api/empire/crawl`, {
            method: 'POST'
        });
        return await response.json();
    }
}

// Uso
const api = new RaidexAPI();

// Iniciar bot
await api.startBot();

// Monitorar logs
setInterval(async () => {
    const status = await api.getStatus();
    console.log('Bot running:', status.running);
    console.log('Latest log:', status.logs[status.logs.length - 1]);
}, 2000);

// Atualizar configuração
await api.updateConfig({
    FLEET_GROUP_NAME: "320 MM",
    COOLDOWN_HOURS: 1.5
});
```

### Script Python para Monitoramento

```python
import requests
import time

class RaidexAPI:
    def __init__(self, base_url='http://localhost:5000'):
        self.base_url = base_url
    
    def get_status(self):
        return requests.get(f'{self.base_url}/api/status').json()
    
    def start_bot(self):
        return requests.post(f'{self.base_url}/api/start').json()
    
    def stop_bot(self):
        return requests.post(f'{self.base_url}/api/stop').json()
    
    def get_cooldowns(self):
        return requests.get(f'{self.base_url}/api/cooldowns').json()
    
    def get_empire_data(self):
        return requests.get(f'{self.base_url}/api/empire/data').json()
    
    def crawl_empire(self):
        return requests.post(f'{self.base_url}/api/empire/crawl').json()

# Uso
api = RaidexAPI()

# Iniciar bot
api.start_bot()

# Monitorar continuamente
while True:
    status = api.get_status()
    if status['logs']:
        print(f"Latest: {status['logs'][-1]}")
    
    cooldowns = api.get_cooldowns()
    print(f"Asteroids in cooldown: {len(cooldowns)}")
    
    time.sleep(5)
```

### Notificações por Telegram

```python
import requests
import time

TELEGRAM_BOT_TOKEN = 'your_bot_token'
TELEGRAM_CHAT_ID = 'your_chat_id'

def send_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    requests.post(url, json={
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    })

api = RaidexAPI()
last_log_count = 0

while True:
    status = api.get_status()
    logs = status['logs']
    
    # Novos logs?
    if len(logs) > last_log_count:
        new_logs = logs[last_log_count:]
        for log in new_logs:
            if '🎯 ASTEROID FOUND' in log or '✅ Mission complete' in log:
                send_telegram(f'🤖 Raidex Bot: {log}')
        last_log_count = len(logs)
    
    time.sleep(10)
```

## 🔒 Considerações de Segurança

> [!WARNING]
> A API atualmente não possui autenticação. Algumas considerações:

1. **Acesso Local Apenas**: Por padrão, o servidor roda em `localhost` e não é acessível externamente
2. **Rede Local**: Se você modificar o `host` para `0.0.0.0` no `web_app.py`, a API ficará acessível na sua rede local
3. **Produção**: Se você pretende expor a API externamente, considere adicionar:
   - Autenticação (Bearer tokens, API keys)
   - HTTPS/SSL
   - Rate limiting
   - CORS adequado

## 📖 Referências

- [README.md](../README.md) - Documentação principal
- [CONFIGURATION.md](CONFIGURATION.md) - Guia de configuração
- [MODULES.md](MODULES.md) - Documentação dos módulos

---

**💡 Dica**: Use ferramentas como [Postman](https://www.postman.com/) ou [Insomnia](https://insomnia.rest/) para testar os endpoints da API interativamente.
