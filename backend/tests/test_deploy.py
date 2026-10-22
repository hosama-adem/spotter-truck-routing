import pytest
from django.core.exceptions import ImproperlyConfigured

from config.deploy import require_production_secret, with_render_host


def test_production_rejects_the_dev_secret():
    with pytest.raises(ImproperlyConfigured):
        require_production_secret(debug=False, secret_key="dev-only-insecure-key")


def test_production_rejects_the_example_placeholder():
    with pytest.raises(ImproperlyConfigured):
        require_production_secret(debug=False, secret_key="replace-me")


def test_production_accepts_a_real_secret():
    require_production_secret(debug=False, secret_key="a-unique-production-secret")


def test_local_debug_keeps_the_dev_secret():
    require_production_secret(debug=True, secret_key="dev-only-insecure-key")


def test_render_host_is_added_once():
    hosts = with_render_host(
        ["spotter-truck-routing-api.onrender.com"],
        "spotter-truck-routing-api.onrender.com",
    )

    assert hosts == ["spotter-truck-routing-api.onrender.com"]
    assert with_render_host(["localhost"], "spotter-truck-routing-api.onrender.com") == [
        "localhost",
        "spotter-truck-routing-api.onrender.com",
    ]
