from pathlib import Path

from vector.embedder import HashEmbedder
from vector.store import JsonVectorStore


def test_json_vector_store_search_returns_best_match(tmp_path):
    store = JsonVectorStore(tmp_path / "vectors.json")
    embedder = HashEmbedder()
    store.upsert("a", embedder.embed("python code"), {"tag": "code"})
    store.upsert("b", embedder.embed("feishu document"), {"tag": "feishu"})

    hits = store.search(embedder.embed("python code"), top_k=1)
    assert hits[0][0] == "a"
    assert hits[0][1] > 0.99


def test_json_vector_store_metadata_filter(tmp_path):
    store = JsonVectorStore(tmp_path / "vectors.json")
    embedder = HashEmbedder()
    store.upsert("x", embedder.embed("git"), {"assistant_id": "work"})
    store.upsert("y", embedder.embed("git"), {"assistant_id": "life"})

    hits = store.search(
        embedder.embed("git"),
        top_k=5,
        metadata_filter={"assistant_id": "work"},
    )
    assert len(hits) == 1
    assert hits[0][0] == "x"
