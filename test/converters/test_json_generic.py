"""TDD — RAG résiduel : le converter JSON doit accepter du JSON générique.

Bug (LANE-B, prouvé en réel sur rag-dev): json_converter n'accepte que le
schéma "article/JDS" (titre/chapeau/texte/_source). Un objet plat et un jsonl
échouent. Ces tests sont écrits AVANT le fix (RED attendu sur flat/jsonl).
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from th2rag.rag.converters.json_converter import convert_json


def _write(tmp_path: str, name: str, content: str) -> str:
    p = os.path.join(tmp_path, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p


def _text_of(result: dict) -> str:
    """Concatène le texte du DoclingDocument produit."""
    doc = result["document"]
    return "\n".join(t.text for t in doc.texts)


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="json_generic_")
    yield d


def test_array_of_records_still_ok(tmp):
    """Non-régression: un tableau d'objets passe (comportement existant)."""
    p = _write(tmp, "arr.json", json.dumps([{"ville": "Metz", "n": 1}, {"ville": "Nancy", "n": 2}]))
    res = convert_json(source=p)
    txt = _text_of(res)
    assert txt.strip(), "tableau: contenu vide"
    # le vrai contenu des records doit être embarqué, pas une métadonnée vide
    assert "Metz" in txt and "Nancy" in txt


def test_flat_object_is_accepted(tmp):
    """Objet JSON plat (clés/valeurs scalaires) → doit être indexé, pas rejeté."""
    p = _write(tmp, "flat.json", json.dumps(
        {"produit": "th2agent", "formats": ["csv", "html", "json"], "note": "ingestion reelle"}))
    res = convert_json(source=p)
    txt = _text_of(res)
    assert txt.strip(), "objet plat: contenu vide"
    # le contenu doit refléter les données réelles de l'objet
    assert "th2agent" in txt and "produit" in txt


def test_jsonl_is_accepted(tmp):
    """NDJSON (un objet par ligne) → doit être parsé ligne par ligne."""
    p = _write(tmp, "lines.jsonl.json",
               '{"ville": "Metz", "n": 1}\n{"ville": "Nancy", "n": 2}\n')
    res = convert_json(source=p)
    txt = _text_of(res)
    assert txt.strip(), "jsonl: contenu vide"
    assert "Metz" in txt and "Nancy" in txt


def test_nested_dict_of_docs_still_ok(tmp):
    """Non-régression: dict dont les valeurs sont des docs article."""
    p = _write(tmp, "nested.json", json.dumps({
        "0": {"titre": "Doc A", "texte": "corps A"},
        "1": {"titre": "Doc B", "texte": "corps B"},
    }))
    res = convert_json(source=p)
    assert _text_of(res).strip(), "nested: contenu vide"


def test_jds_article_without_content_does_not_leak_internal_fields(tmp):
    """Régression BLOQUANTE: un article JDS sans titre/chapeau/texte mais avec
    id_article NE doit PAS dumper _source brut (fuite de champs internes)."""
    p = _write(tmp, "empty_article.json", json.dumps({
        "titre": "", "texte": "", "id_article": "A9",
        "internal_review_notes": "SECRET reviewer comment not for public",
        "internal_author_id": 42,
    }))
    res = convert_json(source=p)
    txt = _text_of(res)
    assert "SECRET" not in txt, "FUITE: champ interne dans le contenu embarqué"
    assert "internal_review_notes" not in txt
    # les champs whitelistés (build_metadata) restent, eux, présents
    assert "A9" in txt


def test_generic_fallback_emits_warning(tmp, caplog):
    """Choix ASSUMÉ: on accepte l'objet plat (feature) MAIS on émet un warning
    observable (un upload accidentel resterait indexé mais visible en logs)."""
    import logging
    p = _write(tmp, "apierr.json", json.dumps({"error": "unauthorized", "code": 401}))
    with caplog.at_level(logging.WARNING):
        res = convert_json(source=p)
    assert _text_of(res).strip()
    assert any("generic document" in r.message or "generic document" in r.getMessage()
               for r in caplog.records), "le fallback générique doit logger un warning"


def test_es_hits_format_still_ok(tmp):
    """Non-régression chemin PROD: format Elasticsearch hits.hits[]._source."""
    p = _write(tmp, "es.json", json.dumps({
        "hits": {"hits": [{"_source": {"titre": "Titre ES", "texte": "corps ES"}}]}
    }))
    res = convert_json(source=p)
    txt = _text_of(res)
    assert "corps ES" in txt


def test_numeric_key_dict_multi_still_ok(tmp):
    """Non-régression chemin PROD: dict à clés numériques → multi-doc combiné."""
    p = _write(tmp, "numeric.json", json.dumps({
        "0": {"titre": "A", "texte": "corps ca"},
        "1": {"titre": "B", "texte": "corps cb"},
    }))
    res = convert_json(source=p)
    txt = _text_of(res)
    assert "corps ca" in txt and "corps cb" in txt
