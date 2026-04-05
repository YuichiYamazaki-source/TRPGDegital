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

### Character Creation

| Command                        | Description                              |
| ------------------------------ | ---------------------------------------- |
| `!cstart`                      | Start character creation                 |
| `!croll`                       | Roll attributes (3d6×5 for each stat)    |
| `!cjob <job_name>`             | Select a job and gain initial skills     |
| `!cskill <skill_name> <value>` | Allocate skill points                    |
| `!cbuy <item_name>`            | Purchase an item and add it to inventory |
| `!cmeta <name>`                | Finalize and save the character          |
| `!cstatus`                     | Show current character creation status   |


---

## Project Structure

```
TRPGgame/
├── main.py                # FastAPI server — REST API endpoints
├── gm.py                  # GM engine — OpenAI GPT-4o-mini integration, rulebook loader, prompt builder
├── session.py             # Session manager — conversation history and state (in-memory)
├── bot.py                 # Discord Bot — command handling and API bridge
├── characters/
│   ├── tanaka.json        # Yuu Tanaka — Private detective (high INT/Spot Hidden)
│   ├── suzuki.json        # Aoi Suzuki — Doctor (high EDU/Medicine)
│   └── yamada.json        # Ren Yamada — Reporter (high APP/Fast Talk)
├── scenarios/
│   ├── scenario_01.md     # "The Midnight Invitation" — original test scenario
│   └── the_haunting.md    # "The Haunting" — introductory scenario from CoC Quick-Start Rules
├── prompts/
│   └── system_prompt.txt  # KP behavior rules and system prompt template ({rules}, {characters}, {scenario})
├── Rule/
│   ├── character_creation.md  # CoC 7e character creation rules (pre-play, for character creation agent)
│   └── game_rules.md         # CoC 7e in-play rules (auto-injected into GM system prompt)
├── docs/
│   ├── before_developing.md   # Coding rules and conventions for all contributors
│   ├── coc-ai-gm-discord-bot-design.md  # System design document
│   └── architecture/
│       ├── gm_agent_architecture.mmd      # GM agent architecture diagram (Mermaid)
│       └── character_create_flow.mmd      # Character creation flow diagram (Mermaid)
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Ruff + mypy configuration
└── .env                   # API keys (not committed)
```

### File Descriptions

| File | Role |
|------|------|
| `main.py` | FastAPI application. Provides `/scenarios`, `/characters`, `/session`, `/session/{id}/chat` endpoints. |
| `gm.py` | Loads rulebook (`Rule/game_rules.md`), builds the system prompt from rules + scenario + characters, sends conversation to OpenAI, returns KP response. |
| `session.py` | Manages session lifecycle and conversation history with a sliding window (last 20 exchanges). |
| `bot.py` | Discord bot using discord.py. Translates Discord commands into API calls and relays KP responses. Supports multi-player sessions via `user_id` → `character_id` mapping. |
| `characters/*.json` | Pre-built investigator sheets with stats (STR, CON, etc.), HP, MP, SAN, and skills. |
| `scenarios/*.md` | Scenario files with locations, NPCs, skill checks, SAN checks, and ending branches. |
| `prompts/system_prompt.txt` | System prompt template injected with `{rules}`, `{characters}`, and `{scenario}` at runtime. |
| `Rule/character_creation.md` | CoC 7th Edition character creation rules — stats, derived attributes, occupations, full skill list with base values. Referenced by the character creation support agent (not loaded by GM at runtime). |
| `Rule/game_rules.md` | CoC 7th Edition in-play rules — skill rolls, SAN, combat, healing, damage tables, skill improvement. Auto-loaded by `gm.py` and injected into the GM system prompt. |
| `docs/before_developing.md` | Coding rules and conventions. **Read before contributing.** |
| `docs/coc-ai-gm-discord-bot-design.md` | System design document covering architecture and component responsibilities. |
| `docs/architecture/*.mmd` | Mermaid diagrams — GM agent architecture and character creation flow. |

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
