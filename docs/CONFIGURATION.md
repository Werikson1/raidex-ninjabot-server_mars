# 📐 Guia de Configuração - Raidex-NinjaBot

Guia completo de todas as opções de configuração do bot, incluindo explicações detalhadas, valores recomendados e dicas de otimização.

## 📋 Índice

- [Arquivo config.json](#-arquivo-configjson)
- [Configurações de URL e Caminhos](#-configurações-de-url-e-caminhos)
- [Configurações de Frota](#-configurações-de-frota)
- [Configurações de Cooldown](#-configurações-de-cooldown)
- [Configurações de Busca](#-configurações-de-busca)
- [Configurações de Tempo de Viagem](#-configurações-de-tempo-de-viagem)
- [Timeouts e Performance](#-timeouts-e-performance)
- [Dicas de Otimização](#-dicas-de-otimização)

## 📄 Arquivo config.json

O arquivo `config.json` localizado na raiz do projeto contém todas as configurações editáveis pelo usuário. O bot recarrega essas configurações a cada ciclo de busca.

### Exemplo Completo

```json
{
    "HEADLESS_MODE": false,
    "FLEET_GROUP_NAME": "300 MM",
    "COOLDOWN_HOURS": 1,
    "SEARCH_DELAY_MIN": 0.3,
    "SEARCH_DELAY_MAX": 1,
    "NO_ASTEROID_WAIT_MIN": 45,
    "NO_ASTEROID_WAIT_MAX": 60,
    "FLEET_FAIL_WAIT_MINUTES": 50,
    "BASE_SYSTEM": 247,
    "TRAVEL_TIME_RANGES": [
        [0, 23, 20],
        [24, 53, 25],
        [54, 103, 30],
        [104, 153, 36],
        [154, 203, 41],
        [204, 499, 45]
    ]
}
```

## 🌐 Configurações de URL e Caminhos

### USE_LOCAL_FILE
- **Tipo**: Boolean
- **Padrão**: `false`
- **Descrição**: Define se o bot deve usar um arquivo HTML local para testes ao invés do site ao vivo
- **Uso**: Desenvolvimento e testes apenas

```json
{
    "USE_LOCAL_FILE": false
}
```

### LOCAL_FILE_PATH
- **Tipo**: String (caminho de arquivo)
- **Padrão**: `"galaxy_view.html"`
- **Descrição**: Caminho para o arquivo HTML local quando `USE_LOCAL_FILE` é `true`

### MAIN_PLANET_ID
- **Tipo**: String (UUID)
- **Padrão**: Auto-detectado
- **Descrição**: ID do planeta/lua principal de onde as frotas serão enviadas
- **Como obter**: Inspecione a URL do jogo quando estiver na visualização da galáxia

```
https://mars.ogamex.net/galaxy?planet=6e3d63fb-afb6-44d4-8440-4768b52cbc3f
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                      Este é o MAIN_PLANET_ID
```

### USER_DATA_DIR
- **Tipo**: String (caminho de diretório)
- **Padrão**: `"user_data"`
- **Descrição**: Diretório onde o perfil persistente do navegador é armazenado
- **Importante**: NÃO delete esta pasta ou você perderá sua sessão de login

### HEADLESS_MODE
- **Tipo**: Boolean
- **Padrão**: `false`
- **Descrição**: Se `true`, o navegador roda invisível (sem janela visual)

**Quando usar**:
- ✅ `false`: Primeiro uso, debugging, quer ver o que o bot está fazendo
- ✅ `true`: Bot em produção, quer economizar recursos

```json
{
    "HEADLESS_MODE": true  // Bot invisível
}
```

> [!WARNING]
> Modo headless pode ser mais facilmente detectado por sistemas anti-bot. Use `false` para maior segurança.

## 🚀 Configurações de Frota

### FLEET_GROUP_NAME
- **Tipo**: String
- **Padrão**: `"320 MM"`
- **Descrição**: Nome do grupo de frotas criado no jogo que será usado para mineração

**Grupos Disponíveis** (pré-configurados):

| Nome | Descrição | Quando Usar |
|------|-----------|-------------|
| `"150 MM"` | 150 Pequeno Cargueiro | Asteroides próximos, economia de deutério |
| `"200 MM"` | 200 Pequeno Cargueiro | Uso geral, asteroides médios |
| `"220 MM"` | 220 Pequeno Cargueiro | Asteroides médios-grandes |
| `"250 MM"` | 250 Pequeno Cargueiro | Asteroides grandes |
| `"300 MM"` | 300 Pequeno Cargueiro | Asteroides muito grandes |
| `"320 MM"` | 320 Pequeno Cargueiro | Máxima capacidade |

**Como configurar**:

1. **No jogo Ogamex**:
   - Vá para a visualização de Frotas
   - Crie um grupo de frotas salvo com o nome exato (ex: "300 MM")
   - Adicione as naves que deseja usar

2. **No config.json**:
   ```json
   {
       "FLEET_GROUP_NAME": "300 MM"
   }
   ```

> [!IMPORTANT]
> O nome do grupo no `config.json` deve corresponder EXATAMENTE ao nome criado no jogo, incluindo maiúsculas/minúsculas.

### FLEET_FAIL_WAIT_MINUTES
- **Tipo**: Number (minutos)
- **Padrão**: `25`
- **Descrição**: Tempo de espera quando o envio da frota falha (ex: nenhuma nave disponível)

**Valores Recomendados**:
- `5-10`: Se você tem muitas frotas e elas retornam rapidamente
- `25-30`: Configuração padrão equilibrada
- `45-60`: Se suas frotas demoram muito para retornar

## 🌌 Configurações de Expedição (Novo)

O bot suporta um modo de expedição automática configurável através do objeto `expedition_mode` no `config.json`.

```json
"expedition_mode": {
    "enabled": true,
    "planet_id": "uuid-do-planeta",
    "fleet_group_name": "Expedition Fleet",
    "fleet_group_value": "uuid-da-frota",
    "headless": false,
    "sleep_mode": true,
    "random_sleep_mode": true,
    "sleep_start": { "hour": 23, "minute": 0 },
    "wake_up": { "hour": 7, "minute": 0 },
    "dispatch_cooldown": { "hour": 1, "minute": 5 }
}
```

### Parâmetros de Expedição

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `enabled` | bool | Ativa/desativa o módulo de expedição |
| `planet_id` | string | UUID do planeta de origem das expedições |
| `fleet_group_name` | string | Nome do grupo de frota a ser enviado |
| `sleep_mode` | bool | Ativa o modo de sono (pausa noturna) |
| `sleep_start` | object | Horário de início do sono `{hour, minute}` |
| `wake_up` | object | Horário de término do sono `{hour, minute}` |
| `dispatch_cooldown` | object | Tempo de espera entre envios `{hour, minute}` |

## ⏱️ Configurações de Cooldown

### COOLDOWN_HOURS
- **Tipo**: Number (horas)
- **Padrão**: `1`
- **Descrição**: Tempo que um asteroide específico fica em cooldown após o envio de uma frota

**Como funciona**:
- Quando uma frota é enviada para `[3:135:17]`, esse asteroide específico entra em cooldown
- O bot não tentará minerar esse asteroide novamente durante `COOLDOWN_HOURS` horas
- Isso evita tentativas duplicadas e economiza tempo de busca

**Valores Recomendados**:
```json
{
    "COOLDOWN_HOURS": 1     // Asteroides duram ~1h geralmente
}
```

> [!TIP]
> Se os asteroides no seu universo duram mais tempo, aumente este valor para 1.5 ou 2 horas.

### Arquivo asteroid_cooldowns.json

Este arquivo é gerado e gerenciado automaticamente pelo bot. Exemplo:

```json
{
    "3:135:17": 1732228800.123,
    "3:220:17": 1732229100.456,
    "3:433:17": 1732229400.789
}
```

- **Chave**: Coordenadas do asteroide `"galaxy:system:position"`
- **Valor**: Timestamp Unix de quando o cooldown expira

> [!NOTE]
> Não edite este arquivo manualmente. O bot gerencia automaticamente e limpa cooldowns expirados.

### Outros Arquivos de Dados

O bot gera e mantém outros arquivos JSON para persistência de estado:

- **`brain_targets.json`**: Armazena as metas de construção definidas na aba "Brain".
- **`expedition_state.json`**: Mantém o estado atual das expedições (contador, timers).
- **`empire_data.json`**: Cache dos dados do seu império (planetas, recursos).
- **`brain_state.db`**: Banco de dados SQLite para rastrear tempos de construção do Brain.

## 🔍 Configurações de Busca

### SEARCH_DELAY_MIN e SEARCH_DELAY_MAX
- **Tipo**: Number (segundos)
- **Padrão**: `0.3` e `1.0`
- **Descrição**: Delay aleatório entre verificações de sistemas durante a busca de asteroides

**Como funciona**:
- Entre cada verificação de sistema (ex: sistema 129, depois 130, depois 131), o bot espera um tempo aleatório entre `SEARCH_DELAY_MIN` e `SEARCH_DELAY_MAX`
- Isso simula comportamento humano e evita detecção

**Valores Recomendados**:

```json
// Busca rápida (mais risco de detecção)
{
    "SEARCH_DELAY_MIN": 0.3,
    "SEARCH_DELAY_MAX": 0.7
}

// Busca balanceada (padrão)
{
    "SEARCH_DELAY_MIN": 0.5,
    "SEARCH_DELAY_MAX": 1.5
}

// Busca muito humana (mais lenta, mais segura)
{
    "SEARCH_DELAY_MIN": 1.0,
    "SEARCH_DELAY_MAX": 3.0
}
```

> [!WARNING]
> Valores muito baixos (< 0.2s) aumentam o risco de detecção como bot!

### NO_ASTEROID_WAIT_MIN e NO_ASTEROID_WAIT_MAX
- **Tipo**: Number (minutos)
- **Padrão**: `25` e `40`
- **Descrição**: Tempo de espera aleatório quando nenhum asteroide é encontrado

**Como funciona**:
- Quando o bot verifica todas as faixas de asteroides e não encontra nenhum disponível (ou todos estão em cooldown), ele espera um tempo aleatório entre esses valores antes de tentar novamente
- Isso evita spam de buscas desnecessárias

**Valores Recomendados**:

```json
// Universo com muitos asteroides
{
    "NO_ASTEROID_WAIT_MIN": 15,
    "NO_ASTEROID_WAIT_MAX": 25
}

// Universo balanceado (padrão)
{
    "NO_ASTEROID_WAIT_MIN": 25,
    "NO_ASTEROID_WAIT_MAX": 40
}

// Universo com poucos asteroides
{
    "NO_ASTEROID_WAIT_MIN": 45,
    "NO_ASTEROID_WAIT_MAX": 60
}
```

## 🚢 Configurações de Tempo de Viagem

### BASE_SYSTEM
- **Tipo**: Number (sistema)
- **Padrão**: `247`
- **Descrição**: Sistema onde seu planeta principal está localizado

**Como obter**:
```
Se seu planeta está em [3:247:8], então BASE_SYSTEM = 247
```

### TRAVEL_TIME_RANGES
- **Tipo**: Array de Arrays `[distância_mín, distância_máx, tempo_requerido]`
- **Descrição**: Define o tempo mínimo de asteroide necessário baseado na distância do seu planeta base

**Como funciona**:
```json
[
    [0, 23, 20],      // Distância 0-23 sistemas: requer 20+ min no asteroide
    [24, 53, 25],     // Distância 24-53 sistemas: requer 25+ min
    [54, 103, 30],    // Distância 54-103 sistemas: requer 30+ min
    [104, 153, 36],   // Distância 104-153 sistemas: requer 36+ min
    [154, 203, 41],   // Distância 154-203 sistemas: requer 41+ min
    [204, 499, 45]    // Distância 204-499 sistemas: requer 45+ min
]
```

**Exemplo prático**:
- Seu planeta está no sistema 247 (`BASE_SYSTEM = 247`)
- Um asteroide aparece no sistema 300
- Distância = |300 - 247| = 53 sistemas
- Pela tabela: distância de 53 cai na faixa `[24, 53, 25]`
- Logo, o asteroide precisa ter **pelo menos 25 minutos** restantes
- Se o asteroide tiver 20 minutos, o bot pula (insuficiente)
- Se tiver 30 minutos, o bot envia a frota ✅

**Como ajustar para seu universo**:

1. **Teste manualmente**:
   - Envie uma frota de teste para um asteroide distante
   - Anote a distância e o tempo de viagem (ida + volta)
   - Adicione uma margem de segurança (5-10 min)

2. **Ajuste a tabela**:
   ```json
   {
       "TRAVEL_TIME_RANGES": [
           [0, 50, 15],      // Asteroides próximos: 15 min suficiente
           [51, 100, 25],    // Médio: 25 min
           [101, 200, 35],   // Longe: 35 min
           [201, 499, 50]    // Muito longe: 50 min
       ]
   }
   ```

> [!TIP]
> Adicione sempre 5-10 minutos de margem de segurança para evitar que a frota chegue após o asteroide desaparecer!

## ⏲️ Timeouts e Performance

### NETWORK_IDLE_TIMEOUT
- **Tipo**: Number (milissegundos)
- **Padrão**: `5000` (5 segundos)
- **Descrição**: Tempo máximo para esperar a rede ficar ociosa após navegação

```json
{
    "NETWORK_IDLE_TIMEOUT": 5000  // 5 segundos
}
```

### FLEET_PAGE_TIMEOUT
- **Tipo**: Number (milissegundos)
- **Padrão**: `10000` (10 segundos)
- **Descrição**: Timeout para carregamento da página de frotas

### MODAL_TIMEOUT
- **Tipo**: Number (milissegundos)
- **Padrão**: `5000` (5 segundos)
- **Descrição**: Timeout para aparecer o modal de asteroides

**Valores Recomendados**:

```json
// Conexão rápida
{
    "NETWORK_IDLE_TIMEOUT": 3000,
    "MODAL_TIMEOUT": 3000
}

// Conexão média (padrão)
{
    "NETWORK_IDLE_TIMEOUT": 5000,
    "MODAL_TIMEOUT": 5000
}

// Conexão lenta
{
    "NETWORK_IDLE_TIMEOUT": 10000,
    "MODAL_TIMEOUT": 10000
}
```

## 💡 Dicas de Otimização

### Para Máxima Segurança (Anti-Detecção)

```json
{
    "HEADLESS_MODE": false,
    "SEARCH_DELAY_MIN": 1.0,
    "SEARCH_DELAY_MAX": 2.5,
    "NO_ASTEROID_WAIT_MIN": 45,
    "NO_ASTEROID_WAIT_MAX": 75
}
```

- Navegador visível parece mais humano
- Delays maiores simulam leitura/decisão humana
- Esperas longas evitam spam de requisições

### Para Máxima Eficiência

```json
{
    "HEADLESS_MODE": true,
    "SEARCH_DELAY_MIN": 0.3,
    "SEARCH_DELAY_MAX": 0.7,
    "NO_ASTEROID_WAIT_MIN": 20,
    "NO_ASTEROID_WAIT_MAX": 30,
    "COOLDOWN_HOURS": 0.75
}
```

- Navegador headless economiza recursos
- Delays curtos aceleram busca
- Cooldowns curtos permitem re-tentativas mais rápidas

> [!CAUTION]
> Configurações muito agressivas aumentam o risco de detecção e possível banimento!

### Para Universos Competitivos

```json
{
    "SEARCH_DELAY_MIN": 0.3,
    "SEARCH_DELAY_MAX": 0.6,
    "NO_ASTEROID_WAIT_MIN": 5,
    "NO_ASTEROID_WAIT_MAX": 10,
    "COOLDOWN_HOURS": 0.5
}
```

- Busca muito rápida para pegar asteroides antes de outros jogadores
- Re-verifica rapidamente para novos asteroides

### Para Economia de Deutério

```json
{
    "FLEET_GROUP_NAME": "150 MM",
    "TRAVEL_TIME_RANGES": [
        [0, 30, 20],      // Só aceita asteroides muito próximos
        [31, 60, 30],
        [61, 100, 999]    // Rejeita asteroides distantes (999 min = impossível)
    ]
}
```

- Frota menor consome menos deutério
- Faixas ajustadas para focar em asteroides próximos apenas

## 📊 Exemplo de Configuração Completa Recomendada

```json
{
    "HEADLESS_MODE": false,
    "FLEET_GROUP_NAME": "300 MM",
    "COOLDOWN_HOURS": 1,
    "SEARCH_DELAY_MIN": 0.5,
    "SEARCH_DELAY_MAX": 1.5,
    "NO_ASTEROID_WAIT_MIN": 30,
    "NO_ASTEROID_WAIT_MAX": 45,
    "FLEET_FAIL_WAIT_MINUTES": 30,
    "BASE_SYSTEM": 247,
    "TRAVEL_TIME_RANGES": [
        [0, 23, 20],
        [24, 53, 25],
        [54, 103, 30],
        [104, 153, 36],
        [154, 203, 41],
        [204, 499, 45]
    ],
    "NETWORK_IDLE_TIMEOUT": 5000,
    "MODAL_TIMEOUT": 5000
}
```

Esta configuração oferece um equilíbrio entre eficiência, segurança e consumo de recursos.

---

**📖 Outros Guias**:
- [README.md](../README.md) - Documentação principal
- [API.md](API.md) - Documentação da API
- [MODULES.md](MODULES.md) - Documentação dos módulos
