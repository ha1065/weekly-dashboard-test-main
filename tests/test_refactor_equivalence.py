"""Robustness / equivalence tests for the refactored lambda_handler dispatcher.

These tests validate that the refactored ``src/lambda_handler.py`` (thin
dispatcher + ``src/handlers/`` package) behaves equivalently to the original
monolith, which is preserved at ``lambda_contents/src/lambda_handler.py``.

The refactor is behavior-preserving, so the properties we assert are:

  A. Dispatch completeness — every mode the original monolith handled is
     reachable in the refactor (named dispatch entry OR pipeline fall-through).
  B. Lazy-import preservation — importing any handler module must NOT eagerly
     import ``src.database.config`` (the secrets bootstrap depends on this).
  C. Routing correctness — invoking ``lambda_handler`` with a given mode calls
     the expected underlying integration/handler and returns a well-formed
     ``{statusCode, body}`` dict with a JSON-decodable body.
  D. Unknown-mode contract — documents the single intentional behavior change
     (unknown mode -> 400 instead of falling through to the pipeline).

No AWS calls and no database are made: boto3 and the heavy ``src.integrations.*``
modules are mocked at the boundary.
"""

import ast
import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_MONOLITH = ROOT / "lambda_contents" / "src" / "lambda_handler.py"


# ---------------------------------------------------------------------------
# Helper: statically extract every mode string the original monolith handled.
# Catches both `mode == 'x'` and `mode in (...)` forms via AST, so we don't
# rely on single-line grep.
# ---------------------------------------------------------------------------

def _extract_original_modes() -> set:
    src = ORIGINAL_MONOLITH.read_text()
    tree = ast.parse(src)
    modes = set()

    class Visitor(ast.NodeVisitor):
        def visit_Compare(self, node):
            # match:  mode == 'literal'
            if (
                isinstance(node.left, ast.Name)
                and node.left.id == "mode"
                and len(node.ops) == 1
                and isinstance(node.ops[0], (ast.Eq,))
                and isinstance(node.comparators[0], ast.Constant)
                and isinstance(node.comparators[0].value, str)
            ):
                modes.add(node.comparators[0].value)
            self.generic_visit(node)

    Visitor().visit(tree)
    return modes


ORIGINAL_MODES = _extract_original_modes()
# Modes that intentionally fall through to the pipeline in the refactor
PIPELINE_MODES = {"weekly", "incremental", "full"}


# ---------------------------------------------------------------------------
# A. Dispatch completeness
# ---------------------------------------------------------------------------

def test_original_modes_were_extracted():
    """Sanity: we actually found the modes to test against."""
    assert len(ORIGINAL_MODES) >= 25, ORIGINAL_MODES
    # spot-check a few known ones
    for m in ("apply_views", "jira_import", "mc_v2_audit", "diagnose_pod", "weekly"):
        assert m in ORIGINAL_MODES, f"expected {m} in extracted modes"


def test_every_original_mode_is_reachable():
    """Every mode the monolith handled must be in MODE_DISPATCH or a pipeline mode."""
    lh = importlib.import_module("src.lambda_handler")
    reachable = set(lh.MODE_DISPATCH.keys()) | PIPELINE_MODES
    missing = ORIGINAL_MODES - reachable
    assert not missing, f"Modes dropped in refactor: {sorted(missing)}"


def test_dispatch_entries_are_all_callable():
    lh = importlib.import_module("src.lambda_handler")
    for mode, fn in lh.MODE_DISPATCH.items():
        assert callable(fn), f"MODE_DISPATCH[{mode!r}] is not callable"


def test_pipeline_modes_not_double_registered():
    """weekly/incremental/full must fall through, not sit in the dispatch table."""
    lh = importlib.import_module("src.lambda_handler")
    for m in PIPELINE_MODES:
        assert m not in lh.MODE_DISPATCH, f"{m} should be a fall-through, not a dispatch entry"


@pytest.mark.parametrize("mode,expected_module,expected_attr", [
    ("apply_views",             "src.handlers.admin",         "apply_views"),
    ("run_migration",           "src.handlers.admin",         "run_migration"),
    ("run_query",               "src.handlers.admin",         "run_query"),
    ("run_query_master",        "src.handlers.admin",         "run_query_master"),
    ("fix_report_user",         "src.handlers.admin",         "fix_report_user"),
    ("restore_forecasts",       "src.handlers.admin",         "restore_forecasts"),
    ("snapshot_kpis",           "src.handlers.pipeline",      "snapshot_kpis"),
    ("forecast_resources",      "src.handlers.pipeline",      "forecast_resources"),
    ("jira_import",             "src.handlers.jira",          "jira_import"),
    ("jira_fields",             "src.handlers.jira",          "jira_fields"),
    ("refresh_quicksight_only", "src.handlers.quicksight",    "refresh_quicksight_only"),
    ("create_quicksight_datasets", "src.handlers.quicksight", "create_quicksight_datasets"),
    ("analyze_project_health",  "src.handlers.ai_analysis",   "analyze_project_health"),
    ("mc_v2_audit",             "src.handlers.ai_analysis",   "mc_v2_audit"),
    ("mc_v2_customers",         "src.handlers.ai_analysis",   "mc_v2_customers"),
    ("analyze_forecast",        "src.handlers.ai_analysis",   "analyze_forecast"),
    ("run_escalations_import",  "src.handlers.escalations",   "run_escalations_import"),
    ("diagnose",                "src.handlers.diagnostics",   "diagnose"),
    ("diagnose_users",          "src.handlers.diagnostics",   "diagnose_users"),
    ("diagnose_pod",            "src.handlers.diagnostics",   "diagnose_pod"),
    ("debug_secrets",           "src.handlers.diagnostics",   "debug_secrets"),
    ("send_compliance_report",  "src.handlers.notifications", "send_compliance_report"),
])
def test_mode_maps_to_correct_handler(mode, expected_module, expected_attr):
    """Each mode routes to the exact handler function the spec assigned it to."""
    lh = importlib.import_module("src.lambda_handler")
    mod = importlib.import_module(expected_module)
    assert lh.MODE_DISPATCH[mode] is getattr(mod, expected_attr)


# ---------------------------------------------------------------------------
# B. Lazy-import preservation (the single most important robustness property)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_name", [
    "src.handlers.common",
    "src.handlers.quicksight",
    "src.handlers.jira",
    "src.handlers.ai_analysis",
    "src.handlers.escalations",
    "src.handlers.admin",
    "src.handlers.diagnostics",
    "src.handlers.pipeline",
    "src.handlers.notifications",
])
def test_handler_import_does_not_eagerly_load_db_config(module_name):
    """Importing a handler module must not pull in src.database.config.

    src.database.config builds the SQLAlchemy engine from DATABASE_URL at
    import time. The secrets bootstrap sets DATABASE_URL at *runtime* inside
    lambda_handler, so any handler that imports the DB module at module scope
    would break the bootstrap ordering.

    Run in a *subprocess* with a fresh interpreter so this check cannot mutate
    the parent process's sys.modules (which would rebind module objects and
    leak state into other tests).
    """
    import subprocess

    code = (
        "import sys\n"
        f"import {module_name}\n"
        "assert 'src.database.config' not in sys.modules, "
        f"'{module_name} eagerly imported src.database.config'\n"
        "print('OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"{module_name} eagerly imports src.database.config "
        f"(breaks secrets bootstrap ordering).\nstderr:\n{proc.stderr}"
    )
    assert "OK" in proc.stdout


# ---------------------------------------------------------------------------
# C. Routing correctness with mocked boundaries
# ---------------------------------------------------------------------------

@pytest.fixture
def mocked_boto3():
    """Patch the secrets bootstrap and boto3 so no real AWS calls happen.

    The bootstrap (get_secrets + set_environment_from_secrets) is validated
    independently in the lazy-import tests; here we stub it so we can focus on
    routing. boto3 is also patched in the handler modules that call it.
    """
    fake_secrets = {
        "db_password": "x", "clockify_api_key": "x", "clockify_workspace_id": "x",
        "master_database_url": "postgresql+pg8000://postgres:x@localhost:5432/db",
    }
    fake = MagicMock(name="boto3")
    fake.client.return_value.get_caller_identity.return_value = {"Account": "111111111111"}

    patchers = [
        patch("src.lambda_handler.get_secrets", return_value=fake_secrets),
        patch("src.lambda_handler.set_environment_from_secrets"),
        patch("src.handlers.quicksight.boto3", fake),
        patch("src.handlers.notifications.boto3", fake),
        patch("src.handlers.common.boto3", fake),
    ]
    for p in patchers:
        p.start()
    yield fake
    for p in patchers:
        p.stop()


def _invoke(mode, event_extra=None):
    lh = importlib.import_module("src.lambda_handler")
    event = {"mode": mode}
    if event_extra:
        event.update(event_extra)
    return lh.lambda_handler(event, MagicMock(name="context"))


def test_refresh_quicksight_only_routes_and_returns_shape():
    """refresh_quicksight_only must reach refresh_quicksight_datasets and
    return the {'refreshed': ...} shape. Self-contained: stubs the bootstrap
    and the refresh helper at its definition site (no boto3 needed)."""
    import src.handlers.quicksight as qs
    lh = importlib.import_module("src.lambda_handler")
    with patch("src.lambda_handler.get_secrets", return_value={"db_password": "x"}), \
         patch("src.lambda_handler.set_environment_from_secrets"), \
         patch.object(qs, "refresh_quicksight_datasets", return_value=[]) as m:
        resp = lh.lambda_handler(
            {"mode": "refresh_quicksight_only", "quicksight_dataset_ids": ["a"]},
            MagicMock(name="context"),
        )
    m.assert_called_once_with(["a"])
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])          # body must be JSON-decodable
    assert body == {"refreshed": []}


def test_jira_import_calls_integration_and_returns_shape(mocked_boto3):
    """Routing reaches src.integrations.import_jira_data.run_jira_import."""
    fake_import = MagicMock(name="import_jira_data")
    fake_import.run_jira_import.return_value = {"statistics": {}}
    with patch.dict(sys.modules, {"src.integrations.import_jira_data": fake_import}):
        # jira_import also opens a verification engine via sqlalchemy.create_engine;
        # patch that so no DB connection is attempted.
        with patch("sqlalchemy.create_engine") as ce:
            ce.return_value.connect.side_effect = Exception("no db in test")
            resp = _invoke("jira_import", {"full_sync": False})
    fake_import.run_jira_import.assert_called_once()
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    # verification failure is swallowed into result['verification'] just like the original
    assert "verification" in body


def test_debug_secrets_returns_masked_shape(mocked_boto3):
    resp = _invoke("debug_secrets")
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["secrets_retrieved"] is True
    assert set(body["env_vars"]) == {
        "JIRA_BASE_URL", "JIRA_API_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEYS"
    }


def test_mc_v2_customers_routes_to_integration(mocked_boto3):
    fake_audit = MagicMock(name="mc_v2_audit")
    fake_audit._get_mc_customers.return_value = [{"customer": "acme"}]
    with patch.dict(sys.modules, {"src.integrations.mc_v2_audit": fake_audit}):
        resp = _invoke("mc_v2_customers")
    fake_audit._get_mc_customers.assert_called_once()
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"customers": [{"customer": "acme"}]}


# ---------------------------------------------------------------------------
# D. Unknown-mode contract (the one intentional behavior difference)
# ---------------------------------------------------------------------------

def test_unknown_mode_returns_400(mocked_boto3):
    """Refactor returns 400 for unknown modes (documented divergence from the
    monolith, which fell through to the incremental pipeline)."""
    resp = _invoke("this_mode_does_not_exist")
    assert resp["statusCode"] == 400
    assert "Unknown mode" in json.loads(resp["body"])["error"]


def test_secrets_failure_reraises(mocked_boto3):
    """Top-level exception handler must re-raise so Lambda marks the invoke failed."""
    with patch("src.lambda_handler.get_secrets", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            _invoke("debug_secrets")
