import main


def test_parse_args_defaults_to_backend_only():
    args = main.parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.with_frontend is False


def test_parse_args_accepts_frontend_flag():
    args = main.parse_args(["--with-frontend", "--port", "8010"])
    assert args.with_frontend is True
    assert args.port == 8010


def test_build_frontend_command_uses_resolved_npm_executable():
    command = main.build_frontend_command(5174, npm_executable="C:/node/npm.cmd")
    assert command == ["C:/node/npm.cmd", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5174"]
