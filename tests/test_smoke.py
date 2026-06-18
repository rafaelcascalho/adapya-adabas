"""Smoke tests for adapya-adabas.

These run without the native Adabas Client Library installed by relying on
the ``ADAPYA_SKIP_NATIVE_LOAD=1`` escape hatch wired into ``api.py``. Tests
that actually exercise database operations live elsewhere and require an
Adabas instance.
"""
import importlib
import os

import pytest

os.environ.setdefault("ADAPYA_SKIP_NATIVE_LOAD", "1")


def test_package_imports():
    pkg = importlib.import_module("adapya.adabas")
    assert pkg.__name__ == "adapya.adabas"


def test_adaerror_module_loads():
    adaerror = importlib.import_module("adapya.adabas.adaerror")
    assert adaerror.__name__ == "adapya.adabas.adaerror"


def test_fields_module_loads():
    fields = importlib.import_module("adapya.adabas.fields")
    assert fields.__name__ == "adapya.adabas.fields"


def test_api_module_loads_without_acl():
    api = importlib.import_module("adapya.adabas.api")
    assert api.__name__ == "adapya.adabas.api"
    assert not api.adalink, "adalink should be falsy when ACL is skipped"


def test_native_call_raises_clear_error():
    api = importlib.import_module("adapya.adabas.api")
    with pytest.raises(api.ProgrammingError, match="libadalnkx"):
        api.adaSetTimeout(1)
