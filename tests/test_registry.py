from pathlib import Path

import pytest

from dqmc_tools.errors import RegistryAmbiguousError, RegistryNotFoundError
from dqmc_tools.registry import (
    list_registry_entries,
    load_registry,
    resolve_observable,
    resolve_registry_entry,
)


def _write_registry(path: Path, entry_id: str, alias: str, dataset_key: str) -> None:
    path.write_text(
        f"""
observables:
  - id: {entry_id}
    aliases: [{alias}]
    code:
      generation:
        variable: {dataset_key}
parameters: []
""".strip(),
        encoding="utf-8",
    )


def test_load_default_registry_and_list_real_entries():
    registry = load_registry()
    entries = list_registry_entries()

    assert "observables" in registry
    assert any(item["id"] == "density" and item["entry_type"] == "observable" for item in entries)
    assert any(item["id"] == "chemical_potential" and item["entry_type"] == "parameter" for item in entries)


def test_resolve_by_id_alias_generation_variable_and_tail():
    by_id = resolve_registry_entry("density")
    by_alias = resolve_registry_entry("n")
    by_variable = resolve_registry_entry("meas_eqlt/density")
    by_tail = resolve_registry_entry("density", entry_type="observable")
    mu = resolve_registry_entry("mu")

    assert by_id["id"] == "density"
    assert by_id["dataset_key"] == "meas_eqlt/density"
    assert by_alias["id"] == "density"
    assert by_variable["id"] == "density"
    assert by_tail["id"] == "density"
    assert mu["id"] == "chemical_potential"
    assert mu["entry_type"] == "parameter"
    assert "repo_id" not in by_id
    assert "h5_path" not in by_id
    assert by_id["source_entry"]["id"] == "density"


def test_resolve_observable_limits_to_observables():
    density = resolve_observable("density")

    assert density["entry_type"] == "observable"
    assert density["id"] == "density"


def test_resolve_missing_name():
    with pytest.raises(RegistryNotFoundError):
        resolve_registry_entry("not_a_registered_entry")


def test_registry_path_is_reloaded_after_file_changes(tmp_path: Path):
    registry_path = tmp_path / "registry.yaml"
    _write_registry(registry_path, "first_density", "hot_density", "meas_eqlt/first_density")

    first = resolve_registry_entry("hot_density", registry_path=registry_path)

    _write_registry(registry_path, "second_density", "hot_density", "meas_eqlt/second_density")
    second = resolve_registry_entry("hot_density", registry_path=registry_path)

    assert first["id"] == "first_density"
    assert first["dataset_key"] == "meas_eqlt/first_density"
    assert second["id"] == "second_density"
    assert second["dataset_key"] == "meas_eqlt/second_density"


def test_registry_env_override_is_used_and_reloaded(tmp_path: Path, monkeypatch):
    registry_path = tmp_path / "registry.yaml"
    monkeypatch.setenv("DQMC_REGISTRY_PATH", str(registry_path))
    _write_registry(registry_path, "env_first", "env_density", "meas_eqlt/env_first")

    first = resolve_registry_entry("env_density")

    _write_registry(registry_path, "env_second", "env_density", "meas_eqlt/env_second")
    second = resolve_registry_entry("env_density")

    assert first["id"] == "env_first"
    assert second["id"] == "env_second"


def test_resolve_ambiguous_tail(tmp_path: Path):
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
observables:
  - id: obs_a
    aliases: []
    code:
      generation:
        variable: meas_eqlt/shared
parameters:
  - id: param_a
    aliases: []
    code:
      generation:
        variable: metadata/shared
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryAmbiguousError) as exc:
        resolve_registry_entry("shared", registry_path=registry_path)

    candidates = exc.value.details["candidates"]
    assert {item["id"] for item in candidates} == {"obs_a", "param_a"}
    assert {item["dataset_key"] for item in candidates} == {"meas_eqlt/shared", "metadata/shared"}
