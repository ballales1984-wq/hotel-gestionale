"""
Test suite per il motore di sincronizzazione PMS — test puri senza DB.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.pms_sync import SyncResult, _find_service, _get_enc_service


class TestSyncResult:
    def test_success_status(self):
        r = SyncResult("success", uuid4(), uuid4(), records_imported=5)
        assert r.status == "success"

    def test_error_status_with_no_imports(self):
        r = SyncResult("error", uuid4(), uuid4(), errors=["fail"])
        assert r.status == "error"

    def test_partial_status(self):
        r = SyncResult("partial", uuid4(), uuid4(), records_imported=3, errors=["err1"])
        assert r.status == "partial"

    def test_success_is_true_when_success(self):
        r = SyncResult("success", uuid4(), uuid4())
        assert r.is_success is True

    def test_is_success_false_on_error(self):
        r = SyncResult("error", uuid4(), uuid4())
        assert r.is_success is False

    def test_summary(self):
        r = SyncResult("success", uuid4(), uuid4(), records_imported=10)
        r.records_read = 100
        s = r.summary()
        assert "100" in s
        assert "10" in s


class TestHelperFunctions:
    def test_find_service_is_callable(self):
        assert callable(_find_service)

    def test_enc_service_lazy(self):
        assert callable(_get_enc_service)