# CoC AI GM — Discord Bot

AI-powered Keeper (KP/GM) for Call of Cthulhu TRPG sessions on Discord.

## Fast Start

### Prerequisites

- Python 3.11+
- Discord Bot token (set in `.env`)
- OpenAI API key (set in `.env`)

### 1. Create and activate a virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure `.env`

```dotenv
OPENAI_API_KEY=your_openai_api_key
DISCORD_TOKEN=your_discord_token
GM_API_BASE_URL=http://localhost:8000
```

### 4. Start the API server (Terminal 1)

```bash
uvicorn main:app --reload
```

Wait for `Application startup complete.` to appear.

### 5. Start the Discord Bot (Terminal 2)

```bash
python bot.py
```

Wait for `Bot ready: ...` to appear.

### 6. Play

Go to the Discord server **Palworld** -> `#trpg-main` and run the commands below.

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
| `!begin` | Start the session and request the KP opening narration |
| `!end` | End the current session |

### Gameplay

| Command | Description |
|---------|-------------|
| `>> <message>` | Speak to the KP as your current character |
| `!check [roll]` | Resolve the current skill or SAN check. If `roll` is omitted, the bot rolls `1d100` for you |
| `!roll` | Roll `1d100` manually |
| `!roll <dice>` | Roll custom dice such as `2d6`, `1d10+5`, or `1d3` |
| `!status` | Show your current HP / MP / SAN, notes, and pending check if it belongs to you |
| `!party` | Show the party-wide HP / MP / SAN summary |
| `!scene` | Show the current scene, summary, clues, flags, and NPC status |

## Gameplay Notes

- Sessions are stateful. The API keeps track of players, HP / MP / SAN, current scene, clues, notes, NPC state, and pending checks.
- While a check is pending, additional `>>` scene actions are blocked until the responsible player resolves it with `!check`.
- `!scene` is the main shared-state view after movement, clue discovery, SAN events, or NPC interaction.
- `!roll` is a free dice utility. `!check` is the command that actually advances the pending skill or SAN check tracked by the session.

### Character Creation

| Command                        | Description                              |
| ------------------------------ | ---------------------------------------- |
| `!cstart`                      | Start character creation                 |
| `!croll`                       | Roll attributes (3d6×5 for each stat)    |
| `!cjob <job_name>`             | Select a job and gain initial skills     |
| `!cskill <skill_name> <value>` | Allocate skill points                    |
| `!cbuy <item_name>`            | Purchase an item and add it to inventory |
| `!cmeta <name>`                | Finalize and save the character          |
| `!cweapons`           | Show available weapon templates              |
| `!cweapon <template>` | Add a weapon from template to your character |
| `!cstatus`                     | Show current character creation status   |





---

## Project Structure

```text
TRPGDegital/
├── main.py                        # FastAPI server — session/state/check endpoints
├── gm.py                          # GM engine — prompt building, metadata parsing, scene inference
├── session.py                     # Session manager — players, environment, NPCs, pending checks
├── dice.py                        # Shared dice parser / roller helpers
├── bot.py                         # Discord bot — command handling and API bridge
├── characters/
│   ├── tanaka.json
│   ├── suzuki.json
│   └── yamada.json
├── scenarios/
│   ├── scenario_01.md
│   └── the_haunting.md
├── Rule/
│   ├── game_rules.md
│   └── character_creation.md
├── prompts/
│   └── system_prompt.txt
├── docs/
│   ├── before_developing.md
│   ├── coc-ai-gm-discord-bot-design.md
│   └── architecture/
│       ├── gm_agent_architecture.mmd
│       └── character_create_flow.mmd
├── requirements.txt
├── pyproject.toml
├── .gitignore
└── .env                           # local only, not committed
```

### File Descriptions

| File | Role |
|------|------|
| `main.py` | FastAPI application. Provides scenario lookup, character lookup, session creation, live state lookup, chat, and pending-check resolution endpoints. |
| `gm.py` | Loads `Rule/game_rules.md`, builds the system prompt from rules, scenario text, character sheets, and live session state, then parses `CHECK:` / `STATE:` metadata from KP responses. |
| `session.py` | Stores in-memory session state including players, environment, NPCs, pending checks, and recent history. |
| `dice.py` | Shared dice rolling helpers used by both the API and Discord bot. |
| `bot.py` | Discord bot using `discord.py`. Converts Discord commands into API calls and relays KP responses and state summaries. |
| `characters/*.json` | Pre-built investigator sheets with stats, derived values, SAN, and skills. |
| `scenarios/*.md` | Scenario files with locations, NPCs, checks, SAN events, and ending branches. |
| `Rule/character_creation.md` | CoC 7th Edition character creation rules for the character creation support flow. |
| `Rule/game_rules.md` | In-play CoC rules reference automatically injected into the GM prompt. |
| `prompts/system_prompt.txt` | System prompt template injected with rules, scenario text, characters, and live state at runtime. |
| `docs/before_developing.md` | Coding rules and conventions. Read before contributing. |
| `docs/coc-ai-gm-discord-bot-design.md` | System design document covering architecture and component responsibilities. |
| `docs/architecture/*.mmd` | Mermaid diagrams for GM agent architecture and character creation flow. |

## Example Session

```bash
!start scenario_01
!join tanaka
!join suzuki
!begin
>> 玄関ホールを調べます
!check
!status
!party
!scene
!end
```
