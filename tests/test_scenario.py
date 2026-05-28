import json
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
        product_name="P1",
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
        assert loaded.blocks[0].product_name == "P1"
        assert result.total_time == 24
        assert result.total_input_quantity == 10
        assert result.final_output_quantity == 10
    finally:
        path.unlink(missing_ok=True)


def test_load_legacy_scenario_defaults_missing_product_name():
    path = Path("tests/.tmp_legacy_scenario.json")
    path.write_text(
        """
{
  "blocks": [
    {
      "id": 1,
      "type": "INPUT",
      "x": 0,
      "y": 0,
      "process_time_per_ea": 30.0,
      "concurrent_capacity": 1,
      "material_name": "A",
      "input_quantity": 10,
      "input_time": 0
    }
  ],
  "connections": []
}
""",
        encoding="utf-8",
    )

    try:
        loaded = load(path)

        assert loaded.blocks[0].product_name == "제품"
    finally:
        path.unlink(missing_ok=True)


def test_legacy_block_types_normalize_on_load_and_save():
    path = Path("tests/.tmp_legacy_types.json")
    normalized_path = Path("tests/.tmp_normalized_types.json")
    path.write_text(
        """
{
  "blocks": [
    {
      "id": 1,
      "type": "INPUT",
      "x": 10,
      "y": 20,
      "process_time_per_ea": 30.0,
      "concurrent_capacity": 1,
      "product_name": "P1",
      "material_name": "A",
      "input_quantity": 6,
      "input_time": 0
    },
    {
      "id": 2,
      "type": "STORAGE",
      "x": 210,
      "y": 20,
      "process_time_per_ea": 2,
      "concurrent_capacity": 2,
      "custom_name": "legacy storage"
    },
    {
      "id": 3,
      "type": "STRAIGHTNESS",
      "x": 410,
      "y": 20,
      "process_time_per_ea": 3,
      "concurrent_capacity": 1
    },
    {
      "id": 4,
      "type": "PRESS",
      "x": 610,
      "y": 20,
      "process_time_per_ea": 4,
      "concurrent_capacity": 1
    }
  ],
  "connections": [
    {"id": 1, "from": 1, "to": 2},
    {"id": 2, "from": 2, "to": 3},
    {"id": 3, "from": 3, "to": 4}
  ]
}
""",
        encoding="utf-8",
    )

    try:
        loaded = load(path)

        assert [block.type for block in loaded.blocks] == [
            "INPUT",
            "WORK_WAITING",
            "INSPECTION",
            "CORRECTION",
        ]
        assert loaded.blocks[1].id == 2
        assert loaded.blocks[1].x == 210
        assert loaded.blocks[1].process_time_per_ea == 2
        assert loaded.blocks[1].concurrent_capacity == 2
        assert loaded.blocks[1].custom_name == "legacy storage"
        assert [(item.from_block, item.to_block) for item in loaded.connections] == [
            (1, 2),
            (2, 3),
            (3, 4),
        ]

        result = simulate(loaded.blocks, loaded.connections)
        assert result.final_output_quantity == 6

        save(loaded, normalized_path)
        saved = json.loads(normalized_path.read_text(encoding="utf-8"))
        assert [block["type"] for block in saved["blocks"]] == [
            "INPUT",
            "WORK_WAITING",
            "INSPECTION",
            "CORRECTION",
        ]
    finally:
        path.unlink(missing_ok=True)
        normalized_path.unlink(missing_ok=True)


def test_save_normalizes_legacy_block_types_from_memory():
    scenario = Scenario()
    scenario.add_block("STORAGE", x=0, y=0, process_time_per_ea=5)
    scenario.add_block("PRESS", x=200, y=0, process_time_per_ea=7)
    path = Path("tests/.tmp_memory_legacy_types.json")

    try:
        save(scenario, path)
        saved = json.loads(path.read_text(encoding="utf-8"))

        assert [block["type"] for block in saved["blocks"]] == [
            "WORK_WAITING",
            "CORRECTION",
        ]
    finally:
        path.unlink(missing_ok=True)
