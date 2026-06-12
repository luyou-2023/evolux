import pytest
from vector.embedder import HashEmbedder
from vector.store import SqliteVecStore, create_vector_store, sqlite_vec_available

pytestmark = pytest.mark.skipif(
    not sqlite_vec_available(),
    reason="sqlite-vec extension unavailable in this Python build",
)


def test_create_vector_store_sqlite_vec_backend(tmp_path):
    store = create_vector_store(tmp_path, "skills.json", backend="sqlite-vec")
    assert isinstance(store, SqliteVecStore)


def test_sqlite_vec_store_search_returns_best_match(tmp_path):
    store = SqliteVecStore(tmp_path / "vector" / "skills.db")
    embedder = HashEmbedder()
    store.upsert("a", embedder.embed("python code"), {"tag": "code"})
    store.upsert("b", embedder.embed("feishu document"), {"tag": "feishu"})

    hits = store.search(embedder.embed("python code"), top_k=1)
    assert hits[0][0] == "a"
    assert hits[0][1] > 0.99


def test_sqlite_vec_store_metadata_filter(tmp_path):
    store = SqliteVecStore(tmp_path / "vector" / "subagents.db")
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
