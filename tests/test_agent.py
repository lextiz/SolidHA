from agent import greet


def test_greet() -> None:
    assert greet() == "hello from agent"
