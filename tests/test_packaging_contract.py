from pathlib import Path


def _section(source: str, start: str) -> str:
    return source.split(start, 1)[1].split("]", 1)[0]


def test_required_torch_runtime_modules_are_not_excluded():
    spec = (Path(__file__).parents[1] / "packaging" / "mapa-roto.spec").read_text(
        encoding="utf-8")
    hidden = _section(spec, "hiddenimports = [")
    excluded = _section(spec, "excludes=[")

    for module in ("torch.distributed", "torch.testing", "lap"):
        assert f'"{module}"' in hidden
        assert f'"{module}"' not in excluded


def test_ultralytics_runtime_tracker_dependency_is_pinned():
    requirements = (Path(__file__).parents[1] / "requirements.txt").read_text(
        encoding="utf-8")
    assert "lap==0.5.13" in requirements
