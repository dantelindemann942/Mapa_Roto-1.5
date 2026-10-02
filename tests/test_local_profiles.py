import json

import pytest

import local_profiles


@pytest.fixture
def isolated_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("MAPA_ROTO_DATA_DIR", str(tmp_path))
    return tmp_path


def test_first_load_creates_all_builtin_profiles(isolated_profiles):
    profiles = local_profiles.list_profiles()
    assert {p["id"] for p in profiles} >= {"mapa-roto", "gaming", "podcast", "tutorial"}
    assert all(p["builtin"] for p in profiles)
    assert json.loads((isolated_profiles / "profiles.json").read_text(encoding="utf-8"))


def test_custom_profile_is_normalised_and_persisted(isolated_profiles):
    saved = local_profiles.create_profile({
        "name": "Mi Estilo",
        "target_clips": 99,
        "min_seconds": 10,
        "max_seconds": 11,
        "layouts": ["split", "evil"],
        "encoder": "qsv",
    })
    assert saved["builtin"] is False
    assert saved["target_clips"] == 15
    assert saved["max_seconds"] >= saved["min_seconds"] + 5
    assert saved["layouts"] == ["split"]
    assert local_profiles.get_profile(saved["id"])["name"] == "Mi Estilo"


def test_builtin_profile_cannot_be_deleted(isolated_profiles):
    local_profiles.list_profiles()
    with pytest.raises(PermissionError):
        local_profiles.delete_profile("mapa-roto")

