# Repository Guidelines

## Project Structure & Module Organization

- `src/pj_assistant/`: main Python package.
  - `config.py`: loads `config.yaml` into typed dataclasses.
  - `assistant.py`: Playwright automation (opens list page, switches teacher tabs, pre-fills form).
- Top-level entrypoints:
  - `run_login.py`: opens the login page and saves browser storage state.
  - `run_assist.py`: runs the semi-automatic assistant (fills but does not submit).
- Configuration:
  - `config.example.yaml`: template.
  - `config.yaml`: local config (URLs, selectors, delays).
- Runtime artifacts:
  - `storage_state*.json`: saved login state per account.
  - `logs/` and `logs/screenshots/`: run logs and failure screenshots.

## Build, Test, and Development Commands

Set up venv and dependencies:

```powershell
cd pj_assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install
```

Login and save session (per account):

```powershell
python run_login.py --config config.yaml --storage storage_state_user2.json
```

Run assistant with a specific session:

```powershell
python run_assist.py --config config.yaml --storage storage_state_user2.json
```

## Coding Style & Naming Conventions

- Python 3.10+.
- Prefer small, focused helper functions in `src/pj_assistant/assistant.py`.
- Use descriptive names (`teacher_tabs`, `modal_scope`, `storage_state_path`) over abbreviations.
- Keep changes minimal and scoped; avoid editing selectors unless necessary.

## Testing Guidelines

No automated test suite is included. Validate changes by running:

- `python -c "import pj_assistant"` (basic import sanity)
- `python run_assist.py --config config.yaml` (manual smoke test on the target portal)

## Commit & Pull Request Guidelines

This workspace does not include a `.git/` history. If you add one:

- Use imperative commit subjects (e.g., “Fix teacher tab switching”).
- In PRs, describe the portal behavior being handled and attach `logs/screenshots/error_*.png` when relevant.

## Security & Configuration Tips

- Do not commit `config.yaml` or `storage_state*.json` to version control (they contain sensitive URLs/cookies).
- The assistant is intentionally semi-automatic: it pre-fills inputs but should not auto-submit evaluations.
