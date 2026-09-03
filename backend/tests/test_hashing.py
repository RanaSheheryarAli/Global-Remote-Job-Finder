from app.ingestion.greenhouse import stable_hash


def test_stable_hash_is_key_order_independent() -> None:
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
