"""
Lot 5 — Observabilité error_message sur Knowledge.

Tests couverts :
1. update_knowledge_status écrit error_message quand fourni.
2. update_knowledge_status ne touche pas error_message quand non fourni.
3. Le schéma Pydantic Knowledge expose error_message (Optional[str]).
4. process_pdfs_sync : tout-FAILED → error_message renseigné sur le Knowledge.
5. process_pdfs_sync : succès partiel → COMPLETED + error_message récap des fichiers ignorés.
6. process_pdfs_background : succès partiel → COMPLETED + error_message récap.
7. process_pdfs_background : tout-FAILED → error_message renseigné.

Aucune connexion à la vraie DB : tout est mocké via AsyncMock/MagicMock.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Tests du modèle SQLAlchemy — vérification de la colonne
# ---------------------------------------------------------------------------

def test_knowledge_model_has_error_message_column():
    """Knowledge doit avoir une colonne error_message de type Text nullable."""
    from th2rag.models import Knowledge
    from sqlalchemy import inspect as sa_inspect, Text

    mapper = sa_inspect(Knowledge)
    col = mapper.columns.get("error_message")
    assert col is not None, "La colonne error_message est absente du modèle Knowledge"
    assert col.nullable is True, "error_message doit être nullable"


# ---------------------------------------------------------------------------
# Tests du schéma Pydantic
# ---------------------------------------------------------------------------

def test_knowledge_schema_exposes_error_message():
    """Le schéma Pydantic Knowledge doit exposer error_message optionnel."""
    from th2rag.knowledge.schemas import Knowledge as KnowledgeSchema
    import inspect

    fields = KnowledgeSchema.model_fields
    assert "error_message" in fields, (
        f"Le champ error_message est absent du schéma Pydantic Knowledge. "
        f"Champs présents : {list(fields.keys())}"
    )
    # Doit être optionnel (default None)
    field = fields["error_message"]
    assert field.default is None or field.is_required() is False, (
        "error_message doit être optionnel (default=None)"
    )


def test_knowledge_schema_error_message_none_by_default():
    """error_message est None quand non renseigné (compatibilité retro)."""
    from th2rag.knowledge.schemas import Knowledge as KnowledgeSchema
    from th2rag.models import Status
    from datetime import datetime

    k = KnowledgeSchema(
        knowledge_id=1,
        name="test",
        description="desc",
        prompt=None,
        user_id=42,
        knowledge_path="/path",
        status=Status.PENDING,
        callback_url=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert k.error_message is None


# ---------------------------------------------------------------------------
# Tests de update_knowledge_status (service)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_knowledge_status_writes_error_message():
    """
    Quand error_message est fourni, update_knowledge_status doit l'écrire
    sur le modèle Knowledge en base.
    """
    from th2rag.knowledge import service
    from th2rag.models import Knowledge, Status

    # Mock de la session DB
    mock_db = AsyncMock()
    fake_knowledge = Knowledge(
        knowledge_id=10,
        name="k",
        description="d",
        knowledge_path="/p",
        knowledge_paths=[],
        filenames=[],
        prompt="p",
        user_id=1,
        status=Status.PENDING,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_knowledge
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    await service.update_knowledge_status(
        knowledge_id=10,
        new_status=Status.FAILED,
        db=mock_db,
        error_message="Document converti mais aucun texte extractible (0 chunks)",
    )

    assert fake_knowledge.status == Status.FAILED
    assert fake_knowledge.error_message == "Document converti mais aucun texte extractible (0 chunks)"
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_knowledge_status_does_not_touch_error_message_when_none():
    """
    Quand error_message n'est pas fourni, le champ existant ne doit pas être
    écrasé (no-op sur ce champ).
    """
    from th2rag.knowledge import service
    from th2rag.models import Knowledge, Status

    mock_db = AsyncMock()
    fake_knowledge = Knowledge(
        knowledge_id=11,
        name="k",
        description="d",
        knowledge_path="/p",
        knowledge_paths=[],
        filenames=[],
        prompt="p",
        user_id=1,
        status=Status.PENDING,
    )
    fake_knowledge.error_message = "message précédent"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_knowledge
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    await service.update_knowledge_status(
        knowledge_id=11,
        new_status=Status.COMPLETED,
        db=mock_db,
        # error_message non fourni → no-op
    )

    assert fake_knowledge.status == Status.COMPLETED
    # Le message précédent ne doit PAS être effacé
    assert fake_knowledge.error_message == "message précédent"


@pytest.mark.asyncio
async def test_update_knowledge_status_truncates_long_error_message():
    """
    Un message très long doit être tronqué à 2000 caractères.
    """
    from th2rag.knowledge import service
    from th2rag.models import Knowledge, Status

    mock_db = AsyncMock()
    fake_knowledge = Knowledge(
        knowledge_id=12,
        name="k",
        description="d",
        knowledge_path="/p",
        knowledge_paths=[],
        filenames=[],
        prompt="p",
        user_id=1,
        status=Status.PENDING,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_knowledge
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    long_message = "x" * 5000
    await service.update_knowledge_status(
        knowledge_id=12,
        new_status=Status.FAILED,
        db=mock_db,
        error_message=long_message,
    )

    assert len(fake_knowledge.error_message) <= 2000


# ---------------------------------------------------------------------------
# Tests process_pdfs_sync — FAILED total
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_pdfs_sync_all_failed_sets_error_message(monkeypatch):
    """
    Quand tous les fichiers échouent, update_knowledge_status doit être appelé
    avec Status.FAILED ET un error_message décrivant la raison.
    """
    import th2rag.rag.tasks.process_pdf as module
    from th2rag.models import Status

    # Mock du processor : process_single_file lève toujours une exception
    mock_processor_instance = MagicMock()
    mock_processor_instance.process_single_file = AsyncMock(
        side_effect=Exception("Document processing failed for s3://x/a.pdf: 0 chunks")
    )
    monkeypatch.setattr(module, "PDFProcessor", lambda: mock_processor_instance)

    captured_calls = []

    async def fake_update_status(knowledge_id, new_status, db, error_message=None):
        captured_calls.append({
            "knowledge_id": knowledge_id,
            "status": new_status,
            "error_message": error_message,
        })

    monkeypatch.setattr(module, "update_knowledge_status", fake_update_status)

    mock_db = AsyncMock()

    with pytest.raises(Exception):
        await module.process_pdfs_sync(
            doc_id=99,
            sources=["s3://bucket/a.pdf"],
            db=mock_db,
        )

    # Au moins un appel avec FAILED doit avoir un error_message non vide
    failed_calls = [c for c in captured_calls if c["status"] == Status.FAILED]
    assert failed_calls, "Aucun appel update_knowledge_status FAILED trouvé"
    assert any(c["error_message"] for c in failed_calls), (
        "update_knowledge_status FAILED doit être appelé avec un error_message non vide"
    )


# ---------------------------------------------------------------------------
# Tests process_pdfs_sync — succès partiel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_pdfs_sync_partial_success_sets_error_message(monkeypatch):
    """
    Succès partiel (1 OK / 1 KO) : statut COMPLETED + error_message récapitulant
    les fichiers ignorés.
    """
    import th2rag.rag.tasks.process_pdf as module
    from th2rag.models import Status

    call_count = {"n": 0}

    async def fake_process_single(doc_id, source, file_index, total_files):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"doc_id": doc_id, "source": source, "chunk_count": 5, "status": "completed"}
        raise Exception(f"Document processing failed for {source}: 0 chunks")

    mock_processor_instance = MagicMock()
    mock_processor_instance.process_single_file = AsyncMock(side_effect=fake_process_single)
    monkeypatch.setattr(module, "PDFProcessor", lambda: mock_processor_instance)

    captured_calls = []

    async def fake_update_status(knowledge_id, new_status, db, error_message=None):
        captured_calls.append({
            "status": new_status,
            "error_message": error_message,
        })

    monkeypatch.setattr(module, "update_knowledge_status", fake_update_status)

    # Mock webhook
    monkeypatch.setattr(module, "send_webhook", AsyncMock())
    monkeypatch.setattr(module, "build_webhook_payload", MagicMock(return_value={}))

    mock_db = AsyncMock()

    result = await module.process_pdfs_sync(
        doc_id=42,
        sources=["s3://bucket/good.pdf", "s3://bucket/bad.pdf"],
        db=mock_db,
    )

    # Statut final doit être COMPLETED
    completed_calls = [c for c in captured_calls if c["status"] == Status.COMPLETED]
    assert completed_calls, "Aucun appel COMPLETED trouvé pour succès partiel"

    # error_message doit récapituler les fichiers ignorés
    partial_call = completed_calls[-1]
    assert partial_call["error_message"] is not None, (
        "error_message doit être renseigné pour le succès partiel"
    )
    assert "bad.pdf" in partial_call["error_message"] or "1/" in partial_call["error_message"] or "ignoré" in partial_call["error_message"], (
        f"error_message doit mentionner les fichiers échoués. Obtenu : {partial_call['error_message']!r}"
    )


# ---------------------------------------------------------------------------
# Tests process_pdfs_background — succès partiel
# ---------------------------------------------------------------------------

def test_process_pdfs_background_partial_success_sets_error_message(monkeypatch):
    """
    process_pdfs_background : succès partiel → update_knowledge_status COMPLETED
    avec un error_message récapitulant les fichiers ignorés.
    """
    import th2rag.rag.tasks.process_pdf as module
    from th2rag.models import Status
    import asyncio

    call_count = {"n": 0}

    async def fake_process_single(doc_id, source, file_index, total_files):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"doc_id": doc_id, "source": source, "chunk_count": 3, "status": "completed"}
        raise Exception(f"Document processing failed for {source}: format non supporté")

    # Mock engine + session
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    # For callback_url lookup
    mock_row = MagicMock()
    mock_row.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_row)

    mock_session_maker = MagicMock(return_value=mock_session)

    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    monkeypatch.setattr(module, "create_async_engine", lambda *a, **kw: mock_engine)
    monkeypatch.setattr(module, "sessionmaker", lambda *a, **kw: mock_session_maker)

    mock_processor_instance = MagicMock()
    mock_processor_instance.process_single_file = AsyncMock(side_effect=fake_process_single)
    monkeypatch.setattr(module, "PDFProcessor", lambda: mock_processor_instance)

    captured_calls = []

    async def fake_update_status(knowledge_id, new_status, db, error_message=None):
        captured_calls.append({
            "status": new_status,
            "error_message": error_message,
        })

    monkeypatch.setattr(module, "update_knowledge_status", fake_update_status)
    monkeypatch.setattr(module, "send_webhook", AsyncMock())
    monkeypatch.setattr(module, "build_webhook_payload", MagicMock(return_value={}))

    module.process_pdfs_background(
        doc_id=55,
        sources=["s3://b/ok.pdf", "s3://b/bad.docx"],
    )

    completed_calls = [c for c in captured_calls if c["status"] == Status.COMPLETED]
    assert completed_calls, "Aucun appel COMPLETED trouvé pour succès partiel background"

    partial_call = completed_calls[-1]
    assert partial_call["error_message"] is not None, (
        "error_message doit être renseigné pour le succès partiel background"
    )


def test_process_pdfs_background_all_failed_sets_error_message(monkeypatch):
    """
    process_pdfs_background : tout FAILED → update_knowledge_status FAILED
    avec un error_message.
    """
    import th2rag.rag.tasks.process_pdf as module
    from th2rag.models import Status

    async def fake_process_single(doc_id, source, file_index, total_files):
        raise Exception(f"Document processing failed for {source}: crash")

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_row = MagicMock()
    mock_row.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_row)
    mock_session_maker = MagicMock(return_value=mock_session)

    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    monkeypatch.setattr(module, "create_async_engine", lambda *a, **kw: mock_engine)
    monkeypatch.setattr(module, "sessionmaker", lambda *a, **kw: mock_session_maker)

    mock_processor_instance = MagicMock()
    mock_processor_instance.process_single_file = AsyncMock(side_effect=fake_process_single)
    monkeypatch.setattr(module, "PDFProcessor", lambda: mock_processor_instance)

    captured_calls = []

    async def fake_update_status(knowledge_id, new_status, db, error_message=None):
        captured_calls.append({
            "status": new_status,
            "error_message": error_message,
        })

    monkeypatch.setattr(module, "update_knowledge_status", fake_update_status)
    monkeypatch.setattr(module, "send_webhook", AsyncMock())
    monkeypatch.setattr(module, "build_webhook_payload", MagicMock(return_value={}))

    module.process_pdfs_background(
        doc_id=66,
        sources=["s3://b/a.pdf"],
    )

    failed_calls = [c for c in captured_calls if c["status"] == Status.FAILED]
    assert failed_calls, "Aucun appel FAILED trouvé pour tout-FAILED background"
    assert any(c["error_message"] for c in failed_calls), (
        "update_knowledge_status FAILED doit avoir un error_message non vide"
    )
