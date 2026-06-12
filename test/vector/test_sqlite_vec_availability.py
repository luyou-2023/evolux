from vector.store import (
    DEFAULT_VECTOR_BACKEND,
    JsonVectorStore,
    SqliteVecStore,
    SqliteVectorStore,
    create_vector_store,
    resolve_vector_backend,
    sqlite_vec_available,
)


def test_default_vector_backend_is_sqlite_vec():
    assert DEFAULT_VECTOR_BACKEND == "sqlite-vec"


def test_resolve_vector_backend_falls_back_to_sqlite_when_vec_unavailable(monkeypatch):
    monkeypatch.setattr("vector.store.sqlite_vec_available", lambda: False)
    assert resolve_vector_backend() == "sqlite"
    assert resolve_vector_backend("sqlite-vec") == "sqlite"


def test_create_vector_store_default_uses_vec_or_sqlite_fallback(tmp_path, monkeypatch):
    if sqlite_vec_available():
        store = create_vector_store(tmp_path, "skills.json")
        assert isinstance(store, SqliteVecStore)
        return

    monkeypatch.setattr("vector.store.sqlite_vec_available", lambda: False)
    store = create_vector_store(tmp_path, "skills.json")
    assert isinstance(store, SqliteVectorStore)


def test_create_vector_store_json_backend_explicit(tmp_path):
    store = create_vector_store(tmp_path, "skills.json", backend="json")
    assert isinstance(store, JsonVectorStore)


def test_sqlite_vec_available_matches_environment():
    assert isinstance(sqlite_vec_available(), bool)
