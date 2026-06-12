from cli.main import main


def test_cli_version():
    assert main(["version"]) == 0
