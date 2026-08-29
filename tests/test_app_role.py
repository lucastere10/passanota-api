import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI

from app.main import mount_routers


def _paths(app: FastAPI) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_http_role_does_not_mount_internal_routes():
    app = FastAPI()
    mount_routers(app, "http")
    paths = _paths(app)
    assert "/v1/dashboard" in paths or any(path.startswith("/v1") for path in paths)
    assert not any(path.startswith("/internal/tasks") for path in paths)
    assert "/internal/encode" not in paths


def test_http_role_process_does_not_import_ml():
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["APP_ROLE"] = "http"
    env["EMBEDDINGS_ENABLED"] = "false"
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.main import app\n"
            "import sys\n"
            "loaded = [m for m in ("
            "'cv2', 'torch', 'sentence_transformers', "
            "'app.services.task_worker', "
            "'app.services.image.preprocessor'"
            ") if m in sys.modules]\n"
            "assert not loaded, loaded\n"
            "assert '/health/live' in {getattr(r, 'path', '') for r in app.routes}\n",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_worker_role_mounts_internal_not_dashboard():
    app = FastAPI()
    mount_routers(app, "worker")
    paths = _paths(app)
    assert any(path.startswith("/internal/tasks") for path in paths)
    assert "/internal/encode" not in paths
    assert not any(path.startswith("/v1/dashboard") for path in paths)


def test_search_module_does_not_import_local_ml():
    import sys

    sys.modules.pop("app.routers.search", None)
    before = set(sys.modules)
    import app.routers.search  # noqa: F401

    loaded = set(sys.modules) - before
    assert "cv2" not in loaded
    assert "app.services.image.preprocessor" not in loaded
    assert "app.services.task_worker" not in loaded
