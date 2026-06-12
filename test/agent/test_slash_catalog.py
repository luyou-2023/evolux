from agent.slash_catalog import slash_completions


def test_slash_completions_root():
    assert "/help" in slash_completions("/h")
    assert "/skills" in slash_completions("/ski")


def test_slash_completions_subcommand():
    assert "/skills browse" in slash_completions("/skills b")
