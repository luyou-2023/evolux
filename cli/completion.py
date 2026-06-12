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
      _message -e 'Use /help and Tab completion for slash commands in chat'
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


def generate_bash_completion() -> str:
    assistants = " ".join(_assistant_ids())
    skills = " ".join(_bundled_skill_names())
    return f"""# Evolux bash completion — add to ~/.bashrc: eval "$(evolux completion bash)"

_evolux_completion() {{
    local cur prev
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"

    if [[ ${{COMP_CWORD}} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "version setup chat tui skills cron acp dashboard assistant gateway completion" -- "$cur") )
        return
    fi

    case "${{COMP_WORDS[1]}}" in
        chat)
            if [[ "$prev" == "--assistant" ]]; then
                COMPREPLY=( $(compgen -W "{assistants or 'default'}" -- "$cur") )
            else
                COMPREPLY=( $(compgen -W "--assistant --once --trace" -- "$cur") )
            fi
            ;;
        skills)
            if [[ ${{COMP_CWORD}} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "list reindex install" -- "$cur") )
            elif [[ "${{COMP_WORDS[2]}}" == "install" && ${{COMP_CWORD}} -eq 3 ]]; then
                COMPREPLY=( $(compgen -W "{skills or 'git plan'}" -- "$cur") )
            fi
            ;;
        completion)
            COMPREPLY=( $(compgen -W "zsh bash" -- "$cur") )
            ;;
        acp|dashboard|gateway)
            if [[ ${{COMP_CWORD}} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "start" -- "$cur") )
            elif [[ "$cur" == "--check" || "$prev" == "start" ]]; then
                COMPREPLY=( $(compgen -W "--check" -- "$cur") )
            fi
            ;;
        *)
            COMPREPLY=()
            ;;
    esac
}}

complete -F _evolux_completion evolux
"""


def run_completion(shell: str) -> int:
    if shell == "zsh":
        print(generate_zsh_completion())
        return 0
    if shell == "bash":
        print(generate_bash_completion())
        return 0
    print(f"unsupported shell: {shell}", flush=True)
    return 1
