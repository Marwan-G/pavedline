import pathlib

from tests.conftest import run_script

EMPTY = "openapi: 3.1.0\ninfo: {title: t, version: '1'}\npaths: {}\n"

WIDGET = """\
openapi: 3.1.0
info: {title: t, version: '1'}
paths:
  /v1/widgets/{id}:
    get:
      operationId: getWidget
      parameters:
        - {name: id, in: path, required: true, schema: {type: string}}
      responses:
        '200':
          description: ok
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    $ref: '#/components/schemas/Widget'
components:
  schemas:
    Widget:
      type: object
      properties:
        id: {type: string}
        label: {type: string}
"""


def check(tmp_path: pathlib.Path, app: str, contract: str, *extra: str) -> tuple[int, str]:
    f = tmp_path / "openapi.yaml"
    f.write_text(contract)
    r = run_script("contract_check.py", "--app", f"tests.contract_apps:{app}", "--contract", str(f), *extra)
    return r.returncode, r.stdout + r.stderr


def test_starter_app_matches_an_empty_contract(tmp_path: pathlib.Path) -> None:
    code, out = check(tmp_path, "plain", EMPTY)
    assert code == 0, out


def test_a_route_only_in_the_app_fails(tmp_path: pathlib.Path) -> None:
    code, out = check(tmp_path, "with_extra_route", EMPTY)
    assert code == 1
    assert "GET /v1/widgets" in out and "not in the contract" in out


def test_contract_operations_not_built_are_listed_not_failed(tmp_path: pathlib.Path) -> None:
    code, out = check(tmp_path, "plain", WIDGET)
    assert code == 0, out
    assert "not built yet" in out and "GET /v1/widgets/{id}" in out
    code, out = check(tmp_path, "plain", WIDGET, "--feature-complete")
    assert code == 1
    assert "not built yet" in out


def test_matching_operation_passes_with_path_params_normalised(tmp_path: pathlib.Path) -> None:
    code, out = check(tmp_path, "with_widget_fields", WIDGET, "--feature-complete")
    assert code == 0, out


def test_response_field_mismatch_fails(tmp_path: pathlib.Path) -> None:
    code, out = check(
        tmp_path,
        "with_widget_fields",
        WIDGET.replace("label: {type: string}", "name: {type: string}"),
    )
    assert code == 1
    assert "data.label" in out and "data.name" in out


def test_usage_errors_exit_2(tmp_path: pathlib.Path) -> None:
    r = run_script(
        "contract_check.py",
        "--app",
        "nope.nothing:app",
        "--contract",
        str(tmp_path / "missing.yaml"),
    )
    assert r.returncode == 2


def test_response_field_type_drift_fails(tmp_path: pathlib.Path) -> None:
    code, out = check(
        tmp_path, "with_widget_fields", WIDGET.replace("label: {type: string}", "label: {type: integer}")
    )
    assert code == 1
    assert "data.label" in out and "integer" in out and "string" in out


def test_nullable_drift_fails(tmp_path: pathlib.Path) -> None:
    code, out = check(
        tmp_path,
        "with_widget_fields",
        WIDGET.replace("label: {type: string}", "label: {type: [string, 'null']}"),
    )
    assert code == 1
    assert "data.label" in out
