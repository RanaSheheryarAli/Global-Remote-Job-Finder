from app.registry import load_phase3_sources
from app.schemas.source import SourceCreate


def test_phase3_registry_has_25_companies_and_remote_ok() -> None:
    definitions = [SourceCreate.model_validate(item) for item in load_phase3_sources()]
    companies = [item for item in definitions if not item.is_aggregator]
    aggregators = [item for item in definitions if item.is_aggregator]

    assert len(companies) == 25
    assert {item.source_type for item in companies} == {"greenhouse", "lever", "ashby"}
    assert {item.name for item in companies if item.is_gcc} == {"Careem", "Tamara"}
    assert len(aggregators) == 1
    assert aggregators[0].source_type == "remoteok"


def test_remote_ok_cannot_disable_required_attribution() -> None:
    payload = next(item for item in load_phase3_sources() if item["source_type"] == "remoteok")
    payload = {**payload, "requires_attribution": False}

    try:
        SourceCreate.model_validate(payload)
    except ValueError as exc:
        assert "requires visible attribution" in str(exc)
    else:
        raise AssertionError("Remote OK validation should require attribution")
