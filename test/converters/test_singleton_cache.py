"""Non-regression : les modeles RAG (Docling + embedding) sont charges UNE
fois et partages, pour eviter la race meta-device "Cannot copy out of meta
tensor" qui faisait echouer des PDF en lot concurrent.
"""

from __future__ import annotations

from docling.datamodel.base_models import InputFormat

import th2rag.rag.converters.pdf_converter as pc
import th2rag.rag.embeddings.sentence_transformer as st


class _FakeConverter:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


def test_converter_cached_per_key(monkeypatch) -> None:
    pc._CONVERTER_CACHE.clear()
    monkeypatch.setattr(pc, "DocumentConverter", _FakeConverter)

    a = pc._get_converter(InputFormat.PDF, False, restrict_format=False)
    b = pc._get_converter(InputFormat.PDF, False, restrict_format=False)
    c = pc._get_converter(InputFormat.PDF, True, restrict_format=False)

    assert a is b           # meme cle -> meme instance
    assert c is not a       # cle differente -> instance distincte
    assert len(pc._CONVERTER_CACHE) == 2


def test_converter_restrict_format_passes_allowed_formats(monkeypatch) -> None:
    pc._CONVERTER_CACHE.clear()
    monkeypatch.setattr(pc, "DocumentConverter", _FakeConverter)

    conv = pc._get_converter(InputFormat.IMAGE, True, restrict_format=True)
    assert conv.kwargs.get("allowed_formats") == [InputFormat.IMAGE]


class _FakeModel:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def get_sentence_embedding_dimension(self) -> int:
        return 768


def test_embedding_model_loaded_once(monkeypatch) -> None:
    st._MODEL_CACHE.clear()
    loads = []
    original = _FakeModel.__init__

    def counting_init(self, *args, **kwargs):
        loads.append(1)
        original(self, *args, **kwargs)

    monkeypatch.setattr(_FakeModel, "__init__", counting_init)
    monkeypatch.setattr(st, "SentenceTransformer", _FakeModel)

    m1 = st._get_shared_model("gtr-t5-large", "/cache")
    m2 = st._get_shared_model("gtr-t5-large", "/cache")

    assert m1 is m2
    assert len(loads) == 1
