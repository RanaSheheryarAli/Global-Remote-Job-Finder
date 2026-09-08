from app.registry import load_phase3_sources
from app.schemas.source import SourceCreate


def test_phase3_registry_has_25_companies_and_five_public_feeds() -> None:
    definitions = [SourceCreate.model_validate(item) for item in load_phase3_sources()]
    companies = [item for item in definitions if not item.is_aggregator]
    aggregators = [item for item in definitions if item.is_aggregator]

    assert len(companies) == 25
    assert {item.source_type for item in companies} == {"greenhouse", "lever", "ashby"}
    assert {item.name for item in companies if item.is_gcc} == {"Careem", "Tamara"}
    assert len(aggregators) == 5
    assert {item.source_type for item in aggregators} == {
        "remoteok",
        "himalayas",
        "jobicy",
        "remotive",
        "wwr",
    }
    assert all(item.requires_attribution for item in aggregators)


def test_public_feeds_cannot_disable_required_attribution() -> None:
    payloads = [item for item in load_phase3_sources() if item["is_aggregator"]]

    for original in payloads:
        payload = {**original, "requires_attribution": False}
        try:
            SourceCreate.model_validate(payload)
        except ValueError as exc:
            assert "requires visible attribution" in str(exc)
        else:
            raise AssertionError(f"{original['name']} should require attribution")
