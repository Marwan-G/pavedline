"""scripts/events_check.py: the register lists every event the code emits."""

import pathlib
import shutil

from tests.conftest import API_DIR, run_script

ROOT = API_DIR.parent.parent
REGISTER = ROOT / "docs" / "observability" / "EVENTS.md"


def product(tmp_path: pathlib.Path) -> pathlib.Path:
    """A copy of the API's app code and the register, to plant mistakes in."""
    shutil.copytree(API_DIR / "app", tmp_path / "services" / "api" / "app")
    (tmp_path / "docs" / "observability").mkdir(parents=True)
    shutil.copy(REGISTER, tmp_path / "docs" / "observability" / "EVENTS.md")
    return tmp_path


def plant(root: pathlib.Path, code: str) -> None:
    (root / "services" / "api" / "app" / "planted.py").write_text(
        "import logging\n\nfrom app.events import log_event\n\nlog = logging.getLogger('p')\n\n\n"
        f"def f(name: str) -> None:\n    {code}\n"
    )


def test_the_shipped_register_matches_the_code() -> None:
    r = run_script("events_check.py", "--root", str(ROOT))
    assert r.returncode == 0, r.stderr
    assert "warning" not in r.stdout


def test_an_unregistered_event_fails(tmp_path: pathlib.Path) -> None:
    root = product(tmp_path)
    plant(root, 'log_event(log, logging.INFO, "job.created")')
    r = run_script("events_check.py", "--root", str(root))
    assert r.returncode == 1
    assert "'job.created' has no row" in r.stderr
    assert "planted.py" in r.stderr


def test_a_computed_name_fails(tmp_path: pathlib.Path) -> None:
    root = product(tmp_path)
    plant(root, "log_event(log, logging.INFO, name)")
    r = run_script("events_check.py", "--root", str(root))
    assert r.returncode == 1
    assert "not a literal string" in r.stderr


def test_a_bad_name_fails(tmp_path: pathlib.Path) -> None:
    root = product(tmp_path)
    plant(root, 'log_event(log, logging.INFO, "JobCreated")')
    r = run_script("events_check.py", "--root", str(root))
    assert r.returncode == 1
    assert "bad event name" in r.stderr


def test_a_duplicate_row_fails(tmp_path: pathlib.Path) -> None:
    root = product(tmp_path)
    md = root / "docs" / "observability" / "EVENTS.md"
    row = next(line for line in md.read_text().splitlines() if line.startswith("| `db.data_error`"))
    md.write_text(md.read_text() + "\n## Events\n\n" + row + "\n")
    r = run_script("events_check.py", "--root", str(root))
    assert r.returncode == 1
    assert "duplicate row" in r.stderr


def test_a_row_the_code_does_not_emit_is_only_a_warning(tmp_path: pathlib.Path) -> None:
    root = product(tmp_path)
    md = root / "docs" / "observability" / "EVENTS.md"
    text = md.read_text().replace(
        "\n## Not covered yet",
        "| `job.created` | info | later | none | planned | no | 2.1 |\n\n## Not covered yet",
    )
    md.write_text(text)
    r = run_script("events_check.py", "--root", str(root))
    assert r.returncode == 0, r.stderr
    assert "lists 'job.created'" in r.stdout


def test_a_missing_register_fails(tmp_path: pathlib.Path) -> None:
    root = product(tmp_path)
    (root / "docs" / "observability" / "EVENTS.md").unlink()
    r = run_script("events_check.py", "--root", str(root))
    assert r.returncode == 1
    assert "is missing" in r.stderr


def test_a_module_named_events_elsewhere_is_scanned(tmp_path: pathlib.Path) -> None:
    root = product(tmp_path)
    (root / "services" / "api" / "app" / "services" / "events.py").write_text(
        "import logging\n\nfrom app.events import log_event\n\n\n"
        "def f() -> None:\n    log_event(logging.getLogger('p'), logging.INFO, 'invoice.paid')\n"
    )
    r = run_script("events_check.py", "--root", str(root))
    assert r.returncode == 1
    assert "'invoice.paid' has no row" in r.stderr


def test_an_import_alias_is_followed(tmp_path: pathlib.Path) -> None:
    root = product(tmp_path)
    (root / "services" / "api" / "app" / "planted.py").write_text(
        "import logging\n\nfrom app.events import log_event as emit\n\n\n"
        "def f() -> None:\n    emit(logging.getLogger('p'), logging.INFO, 'invoice.paid')\n"
    )
    r = run_script("events_check.py", "--root", str(root))
    assert r.returncode == 1
    assert "'invoice.paid' has no row" in r.stderr


def test_a_row_inside_a_code_block_does_not_count(tmp_path: pathlib.Path) -> None:
    root = product(tmp_path)
    plant(root, 'log_event(log, logging.INFO, "job.created")')
    md = root / "docs" / "observability" / "EVENTS.md"
    md.write_text(
        md.read_text().replace(
            "\n## Not covered yet",
            "\n```\n| `job.created` | info | x | none | x | no | 1 |\n```\n\n## Not covered yet",
        )
    )
    r = run_script("events_check.py", "--root", str(root))
    assert r.returncode == 1
    assert "'job.created' has no row" in r.stderr
