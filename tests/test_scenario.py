import pytest
from pathlib import Path

from engine.models import Scenario
from engine.scenario_io import load, save
from engine.simulation import simulate


def test_scenario_rejects_duplicate_and_self_connections():
    scenario = Scenario()
    scenario.add_block("INPUT", x=0, y=0, process_time=30)
    scenario.add_block("CUTTING", x=200, y=0, process_time=45)
    scenario.add_connection(1, 2)

    with pytest.raises(ValueError):
        scenario.add_connection(1, 2)

    with pytest.raises(ValueError):
        scenario.add_connection(1, 1)


def test_delete_block_cascades_connections():
    scenario = Scenario()
    scenario.add_block("INPUT", x=0, y=0, process_time=30)
    scenario.add_block("CUTTING", x=200, y=0, process_time=45)
    scenario.add_block("HEAT", x=400, y=0, process_time=120)
    scenario.add_connection(1, 2)
    scenario.add_connection(2, 3)

    scenario.delete_block(2)

    assert [block.id for block in scenario.blocks] == [1, 3]
    assert scenario.connections == []


def test_save_load_roundtrip_then_simulate():
    scenario = Scenario()
    scenario.add_block("INPUT", x=0, y=0, process_time=30)
    scenario.add_block("CUTTING", x=200, y=0, process_time=45)
    scenario.add_block("HEAT", x=400, y=0, process_time=120)
    scenario.add_connection(1, 2)
    scenario.add_connection(2, 3)

    path = Path("tests/.tmp_scenario.json")
    try:
        save(scenario, path)

        loaded = load(path)
        result = simulate(loaded.blocks, loaded.connections)

        assert loaded == scenario
        assert result.total_time == 1275
    finally:
        path.unlink(missing_ok=True)
