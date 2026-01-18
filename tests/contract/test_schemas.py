import uuid
from datetime import datetime

import pytest

jsonschema = pytest.importorskip("jsonschema")
validate = jsonschema.validate

from libs.platform_lib.schemas import load_schema


def test_user_schema() -> None:
    schema = load_schema("user")
    validate(
        {
            "id": str(uuid.uuid4()),
            "email": "user@example.com",
            "role": "admin",
            "full_name": "Test User",
            "created_at": datetime.utcnow().isoformat(),
        },
        schema,
    )


def test_case_v1_schema() -> None:
    schema = load_schema("case_v1")
    validate(
        {
            "id": str(uuid.uuid4()),
            "title": "Case A",
            "status": "NEW",
            "owner_id": str(uuid.uuid4()),
            "created_at": datetime.utcnow().isoformat(),
        },
        schema,
    )


def test_case_v2_schema() -> None:
    schema = load_schema("case_v2")
    validate(
        {
            "id": str(uuid.uuid4()),
            "title": "Case B",
            "status": "NEW",
            "owner_id": str(uuid.uuid4()),
            "priority": "high",
            "created_at": datetime.utcnow().isoformat(),
        },
        schema,
    )


def test_audit_event_schema() -> None:
    schema = load_schema("audit_event")
    validate(
        {
            "id": str(uuid.uuid4()),
            "event_type": "case_created",
            "payload": {"case_id": str(uuid.uuid4())},
            "created_at": datetime.utcnow().isoformat(),
        },
        schema,
    )
