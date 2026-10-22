"""Aggregate thresholds must be validated before the engine evaluates a diff."""

import subprocess
import sys

import pytest

from diff_contract.contract import ContractParser
from diff_contract.engine import RulesEngine


@pytest.mark.parametrize("field", ["max_files", "max_lines"])
@pytest.mark.parametrize("value", ["15", "many", True, False, 15.0, [], {}])
def test_parser_rejects_non_integer_limits(field, value):
    data = {"rules": [{"name": "valid"}, {"name": "invalid", field: value}]}

    with pytest.raises(ValueError) as exc_info:
        ContractParser().parse(data)

    message = str(exc_info.value)
    assert f"'{field}'" in message
    assert "rule 1" in message
    assert "expected an integer" in message
    assert repr(value) in message


@pytest.mark.parametrize("field", ["max_files", "max_lines"])
@pytest.mark.parametrize("value", [None, -1, 0, 15])
def test_parser_preserves_integer_and_unset_limits(field, value):
    rule = ContractParser().parse({"rules": [{field: value}]}).rules[0]

    assert getattr(rule, field) == value
    assert type(getattr(rule, field)) is type(value)


def test_omitted_limits_remain_unset():
    rule = ContractParser().parse({"rules": [{"name": "no limits"}]}).rules[0]

    assert rule.max_files is None
    assert rule.max_lines is None


@pytest.mark.parametrize("field", ["max_files", "max_lines"])
@pytest.mark.parametrize("yaml_value", ['"15"', "true"])
def test_file_parser_rejects_invalid_yaml_limits(tmp_path, field, yaml_value):
    contract = tmp_path / "contract.yml"
    contract.write_text(f"rules:\n  - {field}: {yaml_value}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=f"Invalid '{field}' value at rule 0"):
        ContractParser().parse_file(contract)


@pytest.mark.parametrize("command", ["check", "validate"])
@pytest.mark.parametrize("field", ["max_files", "max_lines"])
@pytest.mark.parametrize("yaml_value", ['"15"', "true"])
def test_cli_reports_invalid_limit_without_traceback(tmp_path, command, field, yaml_value):
    contract = tmp_path / "contract.yml"
    contract.write_text(f"rules:\n  - {field}: {yaml_value}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "diff_contract.cli",
            command,
            "--contract",
            str(contract),
            "--files",
            "a.py",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "ERROR: Invalid contract" in result.stderr
    assert f"Invalid '{field}' value at rule 0: expected an integer" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("field", ["max_files", "max_lines"])
def test_zero_limit_still_enforces_aggregate_budget(field):
    contract = ContractParser().parse({"rules": [{field: 0}]})

    violations = RulesEngine(contract.rules).check([{"path": "a.py", "lines": 1}])

    assert len(violations) == 1
    assert violations[0].file == "<aggregate>"
