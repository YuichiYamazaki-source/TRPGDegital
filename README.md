# CoC AI GM — Discord Bot

AI-powered Keeper (KP/GM) for Call of Cthulhu TRPG sessions on Discord.

## Fast Start

### Prerequisites

- Python 3.11+
- Discord Bot token (set in `.env`)
- OpenAI API key (set in `.env`)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `.env`

```
OPENAI_API_KEY=your_openai_api_key
DISCORD_TOKEN=your_discord_token
GM_API_BASE_URL=http://localhost:8000
```

### 3. Start the API server (Terminal 1)

```bash
uvicorn main:app --reload
```

Wait for `Application startup complete.` to appear.

### 4. Start the Discord Bot (Terminal 2)

```bash
python bot.py
```

Wait for `Bot ready: ...` to appear.

### 5. Play

Go to the Discord server **Palworld** → `#trpg-main` channel and run the commands below.

---

## Commands

All commands are executed in the `#trpg-main` channel on the **Palworld** Discord server.

### Session Management

| Command | Description |
|---------|-------------|
| `!scenarios` | List available scenarios |
| `!characters` | List available characters with stats |
| `!start <scenario_id>` | Prepare a new session with the specified scenario |
| `!join <character_id>` | Join the session as the specified character |
| `!begin` | Start the session (KP begins the opening narration) |
| `!end` | End the current session |

### Gameplay

| Command | Description |
|---------|-------------|
| `>> <message>` | Send a message to the KP as your character |
| `!roll` | Roll 1d100 (default for CoC skill checks) |
| `!roll <dice>` | Roll custom dice (e.g., `2d6`, `1d10+5`) |

---

## Project Structure

```
TRPGgame/
├── main.py              # FastAPI server — REST API endpoints
├── gm.py                # GM engine — OpenAI GPT-4o-mini integration and prompt builder
├── session.py           # Session manager — conversation history and state (in-memory)
├── bot.py               # Discord Bot — command handling and API bridge
├── characters/
│   ├── tanaka.json      # Yuu Tanaka — Private detective (high INT/Spot Hidden)
│   ├── suzuki.json      # Aoi Suzuki — Doctor (high EDU/Medicine)
│   └── yamada.json      # Ren Yamada — Reporter (high APP/Fast Talk)
├── scenarios/
│   └── scenario_01.md   # "The Midnight Invitation" — test scenario
├── prompts/
│   └── system_prompt.txt  # KP behavior rules and system prompt template
├── docs/
│   └── before_developing.md  # Coding rules and conventions for all contributors
├── requirements.txt     # Python dependencies
├── pyproject.toml       # Ruff + mypy configuration
└── .env                 # API keys (not committed)
```

### File Descriptions

| File | Role |
|------|------|
| `main.py` | FastAPI application. Provides `/scenarios`, `/characters`, `/session`, `/session/{id}/chat` endpoints. |
| `gm.py` | Builds the system prompt from scenario + characters, sends conversation to OpenAI, returns KP response. |
| `session.py` | Manages session lifecycle and conversation history with a sliding window (last 20 exchanges). |
| `bot.py` | Discord bot using discord.py. Translates Discord commands into API calls and relays KP responses. |
| `characters/*.json` | Pre-built investigator sheets with stats (STR, CON, etc.), HP, MP, SAN, and skills. |
| `scenarios/*.md` | Scenario files with locations, NPCs, skill checks, SAN checks, and ending branches. |
| `prompts/system_prompt.txt` | System prompt template injected with `{characters}` and `{scenario}` at runtime. |
| `docs/before_developing.md` | Coding rules and conventions. **Read before contributing.** |

### Example Session

```
!start scenario_01
!join tanaka
!join suzuki
!begin
>> Look around the entrance hall
!roll              → 🎲 1d100 → 43
>> I rolled 43
!end
```
