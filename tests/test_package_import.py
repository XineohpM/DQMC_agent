import sys


def test_package_import_is_agent_independent():
    import dqmc_tools

    assert dqmc_tools.__version__ == "0.1.0"
    assert "app.agent_config" not in sys.modules
    assert "agents" not in sys.modules
    assert "fastapi" not in sys.modules
    assert "mcp" not in sys.modules
