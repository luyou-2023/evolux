"""Shell completion generators for Evolux CLI."""

from __future__ import annotations

from pathlib import Path

from evolux_constants import get_evolux_home
from gateway.assistant_registry import AssistantRegistry


def generate_zsh_completion() -> str:
    assistants = _assistant_ids()
    assistant_words = " ".join(assistants) if assistants else "default"
    bundled = _bundled_skill_names()
    skill_words = " ".join(bundled) if bundled else "git plan"

    return f"""#compdef evolux
# Evolux zsh completion — add to ~/.zshrc: eval "$(evolux completion zsh)"

_evolux() {{
  local -a commands subcmds
  commands=(
    'version:Show version'
    'setup:Initialize ~/.evolux'
    'chat:Interactive orchestrator chat'
    'tui:Terminal status UI'
    'skills:Manage skills'
    'cron:Cron jobs'
    'acp:Editor ACP adapter'
    'dashboard:Web dashboard'
    'assistant:Manage assistants'
    'gateway:Messaging gateway'
    'completion:Shell completion scripts'
  )

  if (( CURRENT == 2 )); then
    _describe 'evolux command' commands
    return
  fi

  case $words[2] in
    chat)
      _arguments \\
        '--assistant[Assistant id]:assistant:({assistant_words})' \\
        '--once[Single turn message]:message:' \\
        '--trace[Show orchestration trace on stderr]'
      ;;
    skills)
      subcmds=(list reindex install)
      if (( CURRENT == 3 )); then
        _describe 'skills command' subcmds
      elif [[ $words[3] == install && CURRENT -eq 4 ]]; then
        _values 'skill name' {skill_words}
      fi
      ;;
    assistant)
      subcmds=(list bind)
      if (( CURRENT == 3 )); then
        _describe 'assistant command' subcmds
      elif [[ $words[3] == bind && CURRENT -eq 4 ]]; then
        _values 'platform' feishu cli
      fi
      ;;
    acp|dashboard|gateway)
      subcmds=(start)
      if (( CURRENT == 3 )); then
        _describe 'subcommand' subcmds
      elif (( CURRENT == 4 )); then
        _arguments '--check[Validate wiring only]'
      fi
      ;;
    completion)
      _values 'shell' zsh bash
      ;;
    *)
      _arguments
      ;;
  esac
}}

_evolux "$@"
"""


def _assistant_ids() -> list[str]:
    try:
        registry = AssistantRegistry(home=get_evolux_home())
        return [item.assistant_id for item in registry.list()]
    except Exception:
        return ["default"]


def _bundled_skill_names() -> list[str]:
    names: set[str] = set()
    root = Path(__file__).resolve().parents[1] / "skills"
    for sub in (root / "bundled", root / "official"):
        if sub.exists():
            names.update(p.name for p in sub.iterdir() if p.is_dir())
    return sorted(names)


def run_completion(shell: str) -> int:
    if shell == "zsh":
        print(generate_zsh_completion())
        return 0
    if shell == "bash":
        print("# bash completion not yet implemented; use: eval \"$(evolux completion zsh)\" in zsh")
        return 0
    print(f"unsupported shell: {shell}", flush=True)
    return 1
