import base64

import httpx
import pytest
from pydantic import ValidationError

from app.main import create_app
from app.settings import Settings
from tests.conftest import client_for

GOOD_SVIX = "whsec_" + base64.b64encode(b"throwaway-key-bytes-0123456789ab").decode()
GOOD_STRIPE = "whsec_stripe_throwaway_secret"
DB = "postgresql://app_runtime:x@127.0.0.1:1/none"


def settings(**kw: object) -> Settings:
    return Settings(app_env="test", database_url=DB, **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_blank_secrets_mean_not_configured(blank: str) -> None:
    s = settings(webhook_clerk_secret=blank, webhook_stripe_secret=blank)
    assert s.webhook_clerk_secret is None
    assert s.webhook_stripe_secret is None


@pytest.mark.parametrize("env", ["WEBHOOK_CLERK_SECRET", "WEBHOOK_STRIPE_SECRET"])
def test_an_empty_environment_variable_is_not_configured(env: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(env, "")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", DB)
    assert Settings().webhook_clerk_secret is None  # pyright: ignore[reportCallIssue]


async def test_blank_secrets_register_no_route() -> None:
    app = create_app(settings(webhook_clerk_secret=" ", webhook_stripe_secret=""))
    try:
        async with client_for(app) as c:
            assert isinstance(c, httpx.AsyncClient)
            assert (await c.post("/webhooks/clerk", content=b"{}")).status_code == 404
            assert (await c.post("/webhooks/stripe", content=b"{}")).status_code == 404
    finally:
        await app.state.engine.dispose()


BAD_SVIX = ["whsec_", "not-whsec", "whsec_!!!notbase64", "whsec_AAAA", "plainbase64AAAAAAAAAAAAAAAA"]


@pytest.mark.parametrize("bad", BAD_SVIX)
def test_a_malformed_svix_secret_fails_at_startup(bad: str) -> None:
    with pytest.raises(ValidationError, match="WEBHOOK_CLERK_SECRET"):
        settings(webhook_clerk_secret=bad)


@pytest.mark.parametrize("bad", ["whsec_", "whsec_short", "a-long-value-without-the-whsec-prefix", "x"])
def test_a_malformed_stripe_secret_fails_at_startup(bad: str) -> None:
    with pytest.raises(ValidationError, match="WEBHOOK_STRIPE_SECRET"):
        settings(webhook_stripe_secret=bad)


def test_well_formed_secrets_are_kept_and_trimmed() -> None:
    s = settings(webhook_clerk_secret=f" {GOOD_SVIX}\n", webhook_stripe_secret=GOOD_STRIPE)
    assert s.webhook_clerk_secret is not None and s.webhook_clerk_secret.get_secret_value() == GOOD_SVIX
    assert s.webhook_stripe_secret is not None


LEAK = "SECRETLEAK7f3a"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("webhook_clerk_secret", f"whsec_!!!{LEAK}"),
        ("webhook_clerk_secret", f"{LEAK}AAAAAAAAAAAAAAAAAAAAAAAA"),  # pasted without the prefix
        ("webhook_clerk_secret", f"whsec_{LEAK}"),
        ("webhook_stripe_secret", f"{LEAK}-no-prefix-at-all"),
        ("webhook_stripe_secret", f"whsec_{LEAK[:3]}"),
    ],
)
def test_a_startup_error_never_contains_the_secret(
    field: str, value: str, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(ValidationError) as info:
        settings(**{field: value})
    # str/repr are what gets printed or logged (`.errors()` is raw data and keeps `input` on purpose)
    seen = [str(info.value), repr(info.value), caplog.text]
    out = capsys.readouterr()
    seen += [out.out, out.err]
    for text in seen:
        assert LEAK not in text
        assert value not in text
    assert field.upper() in str(info.value)  # it says which variable, not what it held


def test_a_malformed_environment_secret_error_hides_it_too(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", DB)
    monkeypatch.setenv("WEBHOOK_CLERK_SECRET", f"whsec_!!!{LEAK}")
    with pytest.raises(ValidationError) as info:
        Settings()  # pyright: ignore[reportCallIssue]
    assert LEAK not in str(info.value) + repr(info.value)


def test_signature_errors_do_not_contain_the_secret() -> None:
    from app.services.webhook_signatures import verify_stripe, verify_svix

    for call in (
        lambda: verify_svix(
            f"whsec_!!!{LEAK}",
            body=b"{}",
            svix_id="m",
            svix_timestamp="1",
            svix_signature="v1,x",
            now=1,
        ),
        lambda: verify_stripe(LEAK[:3], body=b"{}", signature_header="t=1,v1=00", now=1),
    ):
        with pytest.raises(ValueError, match="webhook secret") as info:
            call()
        assert LEAK not in repr(info.value) and LEAK[:3] not in str(info.value)
