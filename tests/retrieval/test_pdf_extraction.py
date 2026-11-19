"""PDF extraction and indexing tests."""

from __future__ import annotations

import io
from pathlib import Path

from core.db import init_db
from core.knowledge.service import KnowledgeService
from core.retrieval.extractors import extract_pdf_text
from core.retrieval.service import RetrievalService, describe_index_result
from tests.test_telegram_onboarding_uploads import _minimal_pdf


def test_extract_text_from_pdf(tmp_path: Path) -> None:
    path = tmp_path / "a.pdf"
    path.write_bytes(_minimal_pdf("backpropagation chain rule"))
    text = extract_pdf_text(path, max_chars=1000)
    assert text is not None and "backpropagation" in text


def test_extract_respects_char_cap(tmp_path: Path) -> None:
    path = tmp_path / "a.pdf"
    path.write_bytes(_minimal_pdf("abcdefghij" * 10))
    assert len(extract_pdf_text(path, max_chars=20) or "") <= 20


def test_corrupt_pdf_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.4 not really a pdf")
    assert extract_pdf_text(path, max_chars=1000) is None


def test_encrypted_pdf_returns_none(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.encrypt("secret")
    buf = io.BytesIO()
    writer.write(buf)
    path = tmp_path / "enc.pdf"
    path.write_bytes(buf.getvalue())
    assert extract_pdf_text(path, max_chars=1000) is None


def test_registered_pdf_is_searchable_and_corrupt_is_skipped(tmp_path: Path) -> None:
    db = tmp_path / "atenas.sqlite"
    init_db(db)
    service = RetrievalService(db, ollama_model="m", allowed_file_roots=[tmp_path])
    knowledge = KnowledgeService(db, allowed_file_roots=[tmp_path])
    good = tmp_path / "good.pdf"
    good.write_bytes(_minimal_pdf("convolution kernels detect edges"))
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"garbage")
    knowledge.register_file(path=str(good))
    knowledge.register_file(path=str(bad))

    sources, error = service.retrieve_sources("convolution kernels")
    assert error is None
    assert sources and "convolution" in sources[0].text.lower()
    stats = service.sync_index()
    assert stats.files_indexed == 1 and stats.skipped_files == 1


def test_describe_index_result() -> None:
    assert "3 chunks" in describe_index_result(True, 3, "a.pdf")
    assert "not searchable" in describe_index_result(False, 0, "a.docx")
    assert "no readable text" in describe_index_result(False, 0, "a.pdf")
