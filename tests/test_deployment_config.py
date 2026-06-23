from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCKER_COMPOSE = PROJECT_ROOT / "docker-compose.yml"


def test_docker_compose_does_not_ship_weak_secret_defaults():
    content = DOCKER_COMPOSE.read_text(encoding="utf-8")

    assert "testagent2026" not in content
    assert "change-this-to-a-random-string-in-production" not in content
    assert "${DB_PASSWORD:-" not in content
    assert "${SECRET_KEY:-" not in content
