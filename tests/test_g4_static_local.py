from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = tuple(ROOT.glob("BLUEPRINT*.md"))


def test_static_forbidden_runtime_paths_are_absent_from_minimum_slice():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "runtime_slice").glob("*.py")
        if path.name != "isolation.py"
    )
    forbidden = ("redis.Redis", "pymysql", "clickhouse_driver", "ccxt", "requests", "boto3")
    assert not any(token in source for token in forbidden)


def test_blueprint_g4_evidence_artifact_exists():
    assert (ROOT / "G4-EVIDENCE-STATIC-LOCAL.md").exists()
    assert BLUEPRINTS
