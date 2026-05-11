"""Tests for API endpoints."""
import pytest
import asyncio
from decimal import Decimal
from uuid import uuid4

from app.main import create_app
from fastapi.testclient import TestClient

