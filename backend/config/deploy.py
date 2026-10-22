from django.core.exceptions import ImproperlyConfigured

INSECURE_SECRET_KEYS = frozenset({"", "dev-only-insecure-key", "replace-me"})


def require_production_secret(*, debug: bool, secret_key: str) -> None:
    if debug or secret_key not in INSECURE_SECRET_KEYS:
        return
    raise ImproperlyConfigured(
        "Set DJANGO_SECRET_KEY to a unique value when DJANGO_DEBUG is false."
    )


def with_render_host(hosts: list[str], render_host: str) -> list[str]:
    if render_host and render_host not in hosts:
        return [*hosts, render_host]
    return list(hosts)
