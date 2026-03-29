# Before Developing

Rules and conventions for all contributors, including AI agents (Claude, Codex).
Read this document before writing any code.

---

## 1. Language Rules

| Context | Language |
|---------|----------|
| Discussion, Discord, PR comments | Japanese |
| Code, comments, docstrings | English |
| Commit messages | English |
| Documentation (README, docs/) | English |
| Game content (scenarios, prompts, character names) | Japanese |

---

## 2. Code Style

### Tooling

| Tool | Purpose | Command |
|------|---------|---------|
| Ruff | Formatter + Linter | `ruff format .` / `ruff check .` |
| mypy | Type checker | `mypy main.py gm.py session.py bot.py` |

All settings are in `pyproject.toml`. Run both before committing.

### Conventions

- Python 3.11+ features allowed (`match`, `X | None`, `type` aliases)
- Use `from __future__ import annotations` in all modules
- Type annotations required for all function signatures
- Line length: 120 characters max
- Quotes: double quotes (`"`)
- Imports: sorted by `isort` rules (handled by Ruff)

### Naming

| Item | Convention | Example |
|------|-----------|---------|
| Files/modules | snake_case | `session.py`, `gm.py` |
| Classes | PascalCase | `SessionManager`, `GMEngine` |
| Functions/methods | snake_case | `create_session()`, `_build_system_prompt()` |
| Constants | UPPER_SNAKE_CASE | `HISTORY_WINDOW`, `SCENARIOS_DIR` |
| Private members | leading underscore | `_sessions`, `_scenario_cache` |

---

## 3. Git & Commit Rules

### Commit Message Format

```
<type>: <description in English>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

Examples:
```
feat: add dice roll command to Discord bot
fix: handle None response from OpenAI API
refactor: extract APIClient class in bot.py
docs: add project structure to README
```

### Branch Strategy

- `main` — stable, working code
- Feature branches: `feat/<short-description>`
- Fix branches: `fix/<short-description>`

### Before Committing

1. `ruff format .`
2. `ruff check .`
3. `mypy main.py gm.py session.py bot.py`
4. Verify the API starts: `uvicorn main:app`
5. Verify the Bot starts: `python bot.py`

---

## 4. AI Agent Rules (Claude / Codex)

Considering...

---

## 5. File Organization

### Where to Put Things (you can customize)

| Content                  | Location                     |
| ------------------------ | ---------------------------- |
| API endpoints            | `main.py`                    |
| LLM logic                | `gm.py`                      |
| Session/state management | `session.py`                 |
| Discord bot commands     | `bot.py`                     |
| Character data           | `characters/<name>.json`     |
| Scenario data            | `scenarios/<scenario_id>.md` |
| System prompts           | `prompts/`                   |
| Documentation            | `docs/`                      |
| Configuration            | `pyproject.toml`, `.env`     |

### Adding a New Character (you can improve)

Create a JSON file in `characters/` with this structure:

```json
{
  "id": "unique_id",
  "name": "Name in Japanese",
  "occupation": "Occupation in Japanese",
  "age": 30,
  "stats": { "STR": 50, "CON": 50, "SIZ": 50, "DEX": 50, "APP": 50, "INT": 50, "POW": 50, "EDU": 50 },
  "hp": 10,
  "mp": 10,
  "san": 50,
  "skills": { "Skill Name": 50 }
}
```

### Adding a New Scenario

Create a markdown file in `scenarios/` with:
- First line: `# Scenario Title` (parsed for listing)
- Sections: overview, locations, skill checks, SAN checks, endings, NPCs

---

## 6. Testing

### Manual Testing (Current)

1. Start API: `uvicorn main:app --reload`
2. Start Bot: `python bot.py`
3. Test in Discord **Palworld** → `#trpg-main`
4. Run through: `!start` → `!join` → `!begin` → `>>` messages → `!roll` → `!end`

### API Testing (curl)

```bash
# List characters
curl http://localhost:8000/characters

# Create session
curl -X POST http://localhost:8000/session \
  -H "Content-Type: application/json" \
  -d '{"channel_id": "test", "scenario_id": "scenario_01", "character_ids": ["tanaka"]}'

# Chat
curl -X POST http://localhost:8000/session/{session_id}/chat \
  -H "Content-Type: application/json" \
  -d '{"character_id": "tanaka", "message": "Hello"}'
```
