from cli.completion import generate_zsh_completion


def test_zsh_completion_includes_commands():
    script = generate_zsh_completion()
    assert "#compdef evolux" in script
    assert "chat" in script
    assert "--trace" in script
    assert "completion" in script


def test_bash_completion_includes_complete_function():
    from cli.completion import generate_bash_completion

    script = generate_bash_completion()
    assert "complete -F _evolux_completion evolux" in script
    assert "chat" in script
