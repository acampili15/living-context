import pytest

from conftest import PLUGIN_ROOT, import_module_from_path

hook = import_module_from_path(
    "context_update_hook", PLUGIN_ROOT / "hooks" / "context-update.py",
)


@pytest.mark.parametrize("command", [
    "git commit -m 'fix bug'",
    'git commit -m "fix bug"',
    "git commit --amend",
    "cd sub && git commit -m x",
    "cd sub; git commit -m x",
    "some-setup && git commit -m x",
    "some-setup || git commit -m x",
    "git -C /some/repo commit -m x",
    "  git commit -m x",
    "git commit",
])
def test_should_process_matches_git_commit_invocations(command):
    data = {"tool_name": "Bash", "tool_input": {"command": command}}
    assert hook._should_process(data) is True


@pytest.mark.parametrize("command", [
    "git status",
    "echo 'do not git commit yet'",
    "git log --grep='git commit'",
    "git commit --dry-run -m x",
    "git commit-msg-hook.sh",
])
def test_should_process_rejects_non_commit_or_dry_run(command):
    data = {"tool_name": "Bash", "tool_input": {"command": command}}
    assert hook._should_process(data) is False


def test_should_process_requires_bash_tool():
    data = {"tool_name": "Write", "tool_input": {"command": "git commit -m x"}}
    assert hook._should_process(data) is False


def test_should_process_requires_success():
    data = {
        "tool_name": "Bash",
        "tool_success": False,
        "tool_input": {"command": "git commit -m x"},
    }
    assert hook._should_process(data) is False


def test_should_process_defaults_success_to_true_when_absent():
    data = {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}
    assert hook._should_process(data) is True


def test_should_process_handles_missing_tool_input():
    data = {"tool_name": "Bash"}
    assert hook._should_process(data) is False
