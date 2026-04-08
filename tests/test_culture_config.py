import os
import tempfile

import pytest


def test_agent_config_defaults():
    """AgentConfig has correct defaults and computed properties."""
    from culture.config import AgentConfig

    agent = AgentConfig()
    assert agent.suffix == ""
    assert agent.backend == "claude"
    assert agent.channels == ["#general"]
    assert agent.model == "claude-opus-4-6"
    assert agent.thinking == "medium"
    assert agent.system_prompt == ""
    assert agent.tags == []
    assert agent.icon is None
    assert agent.archived is False
    assert agent.extras == {}
    # Computed fields
    assert agent.nick == ""
    assert agent.directory == "."
    # Backward compat
    assert agent.agent == "claude"


def test_agent_config_acp_command_from_extras():
    """ACP command is read from extras dict."""
    from culture.config import AgentConfig

    agent = AgentConfig(extras={"acp_command": ["cline", "--acp"]})
    assert agent.acp_command == ["cline", "--acp"]

    # Default when not in extras
    agent2 = AgentConfig()
    assert agent2.acp_command == ["opencode", "acp"]


def test_server_config_defaults():
    """ServerConfig has correct defaults."""
    from culture.config import ServerConfig, ServerConnConfig

    config = ServerConfig()
    assert config.server.name == "culture"
    assert config.server.host == "localhost"
    assert config.server.port == 6667
    assert config.buffer_size == 500
    assert config.poll_interval == 60
    assert config.manifest == {}
    assert config.agents == []


def test_server_config_get_agent():
    """get_agent() looks up by nick."""
    from culture.config import AgentConfig, ServerConfig

    config = ServerConfig(
        agents=[
            AgentConfig(suffix="culture", nick="spark-culture"),
            AgentConfig(suffix="daria", nick="spark-daria"),
        ]
    )
    assert config.get_agent("spark-culture").suffix == "culture"
    assert config.get_agent("spark-daria").suffix == "daria"
    assert config.get_agent("nonexistent") is None


def test_daemon_config_alias():
    """DaemonConfig is an alias for ServerConfig."""
    from culture.config import DaemonConfig, ServerConfig

    assert DaemonConfig is ServerConfig


def test_load_culture_yaml_single_agent(tmp_path):
    """Load single-agent culture.yaml."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("""\
suffix: myagent
backend: claude
model: claude-opus-4-6
channels: ["#general", "#dev"]
thinking: medium
system_prompt: "You are helpful."
tags: [test]
""")
    agents = load_culture_yaml(str(tmp_path))
    assert len(agents) == 1
    assert agents[0].suffix == "myagent"
    assert agents[0].backend == "claude"
    assert agents[0].model == "claude-opus-4-6"
    assert agents[0].channels == ["#general", "#dev"]
    assert agents[0].thinking == "medium"
    assert agents[0].system_prompt == "You are helpful."
    assert agents[0].tags == ["test"]
    assert agents[0].directory == str(tmp_path)


def test_load_culture_yaml_multi_agent(tmp_path):
    """Load multi-agent culture.yaml with agents list."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("""\
agents:
  - suffix: culture
    backend: claude
    model: claude-opus-4-6
  - suffix: codex
    backend: codex
    model: gpt-5.4
""")
    agents = load_culture_yaml(str(tmp_path))
    assert len(agents) == 2
    assert agents[0].suffix == "culture"
    assert agents[0].backend == "claude"
    assert agents[1].suffix == "codex"
    assert agents[1].backend == "codex"
    assert agents[1].model == "gpt-5.4"


def test_load_culture_yaml_by_suffix(tmp_path):
    """Load specific agent from multi-agent culture.yaml."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("""\
agents:
  - suffix: culture
    backend: claude
  - suffix: codex
    backend: codex
""")
    agents = load_culture_yaml(str(tmp_path), suffix="codex")
    assert len(agents) == 1
    assert agents[0].suffix == "codex"


def test_load_culture_yaml_extras(tmp_path):
    """Unknown fields stored in extras dict."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("""\
suffix: daria
backend: acp
model: claude-sonnet-4-6
acp_command: ["opencode", "acp"]
custom_field: hello
""")
    agents = load_culture_yaml(str(tmp_path))
    assert agents[0].acp_command == ["opencode", "acp"]
    assert agents[0].extras["custom_field"] == "hello"


def test_load_culture_yaml_missing_file(tmp_path):
    """Missing culture.yaml raises FileNotFoundError."""
    from culture.config import load_culture_yaml

    with pytest.raises(FileNotFoundError):
        load_culture_yaml(str(tmp_path))


def test_load_culture_yaml_suffix_not_found(tmp_path):
    """Requesting nonexistent suffix raises ValueError."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("suffix: culture\nbackend: claude\n")

    with pytest.raises(ValueError, match="not found"):
        load_culture_yaml(str(tmp_path), suffix="nonexistent")
