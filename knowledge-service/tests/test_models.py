"""Model and migration sanity checks.

Run with: pytest -q tests/test_models.py
"""
import uuid

import pytest


def test_phase1_tables_registered():
    from models.base import Base
    tables = set(Base.metadata.tables.keys())
    for required in ("reports", "conversations", "messages", "message_citations"):
        assert required in tables, f"missing table: {required}"


def test_phase3_dual_library_fields():
    from models.base import Document, Chunk
    doc_cols = {c.name for c in Document.__table__.columns}
    chunk_cols = {c.name for c in Chunk.__table__.columns}
    assert "scope" in doc_cols, "Document.scope missing"
    assert "user_id" in doc_cols, "Document.user_id missing"
    assert "scope" in chunk_cols, "Chunk.scope missing"


def test_report_status_error_fields():
    from models.base import Report
    cols = {c.name for c in Report.__table__.columns}
    assert "status" in cols
    assert "error" in cols
    assert "content_json" in cols
    assert "citations_json" in cols


def test_message_citation_relations():
    from models.base import Conversation, Message, MessageCitation
    conv_rels = {r.mapper.class_.__name__ for r in Conversation.__mapper__.relationships}
    msg_rels = {r.mapper.class_.__name__ for r in Message.__mapper__.relationships}
    assert "Message" in conv_rels
    assert "MessageCitation" in msg_rels
    assert "Conversation" in msg_rels


def test_relationship_cascade_settings():
    from models.base import Conversation
    rel = next(r for r in Conversation.__mapper__.relationships if r.mapper.class_.__name__ == "Message")
    assert rel.cascade.delete, "Message cascade-delete not configured"


def test_uuid_defaults_present():
    from models.base import Report, Conversation, Message, MessageCitation
    for model in (Report, Conversation, Message, MessageCitation):
        pk = model.__table__.primary_key.columns[0]
        assert pk.default is not None, f"{model.__name__} missing UUID default"
        sample = pk.default.arg({})
        assert isinstance(sample, uuid.UUID)
