import pytest
from pathlib import Path

from engine.models import Scenario
from engine.scenario_io import load, save
from engine.simulation import simulate


def test_scenario_rejects_duplicate_self_and_input_target_connections():
    scenario = Scenario()
    scenario.add_block("INPUT", x=0, y=0, material_name="A", input_quantity=10)
    scenario.add_block("CUTTING", x=200, y=0, process_time_per_ea=1)
    scenario.add_connection(1, 2)

    with pytest.raises(ValueError):
        scenario.add_connection(1, 2)

    with pytest.raises(ValueError):
        scenario.add_connection(1, 1)

    with pytest.raises(ValueError, match="원자재 투입 블록"):
        scenario.add_connection(2, 1)


def test_scenario_rejects_cycle_connections():
    scenario = Scenario()
    scenario.add_block("INPUT", x=0, y=0, material_name="A", input_quantity=10)
    scenario.add_block("CUTTING", x=200, y=0, process_time_per_ea=1)
    scenario.add_block("HEAT", x=400, y=0, process_time_per_ea=1)
    scenario.add_connection(1, 2)
    scenario.add_connection(2, 3)

    with pytest.raises(ValueError):
        scenario.add_connection(3, 2)


def test_delete_block_cascades_connections():
    scenario = Scenario()
    scenario.add_block("INPUT", x=0, y=0, material_name="A", input_quantity=10)
    scenario.add_block("CUTTING", x=200, y=0, process_time_per_ea=1)
    scenario.add_block("HEAT", x=400, y=0, process_time_per_ea=1)
    scenario.add_connection(1, 2)
    scenario.add_connection(2, 3)

    scenario.delete_block(2)

    assert [block.id for block in scenario.blocks] == [1, 3]
    assert scenario.connections == []


def test_save_load_roundtrip_then_simulate_bundle_scenario():
    scenario = Scenario()
    scenario.add_block(
        "INPUT",
        x=0,
        y=0,
        material_name="A",
        input_quantity=10,
        input_time=5,
    )
    scenario.add_block(
        "CUTTING",
        x=200,
        y=0,
        process_time_per_ea=1,
        concurrent_capacity=1,
    )
    scenario.add_block(
        "HOIST",
        x=400,
        y=0,
        transport_capacity=4,
        transport_time=3,
    )
    scenario.add_connection(1, 2)
    scenario.add_connection(2, 3)

    path = Path("tests/.tmp_scenario.json")
    try:
        save(scenario, path)

        loaded = load(path)
        result = simulate(loaded.blocks, loaded.connections)

        assert loaded == scenario
        assert result.total_time == 24
        assert result.total_input_quantity == 10
        assert result.final_output_quantity == 10
    finally:
        path.unlink(missing_ok=True)
