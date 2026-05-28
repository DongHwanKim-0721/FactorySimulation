from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ProcessBlock, ProcessConnection, Scenario


LEGACY_BLOCK_TYPE_MAP = {
    "STORAGE": "WORK_WAITING",
    "STRAIGHTNESS": "INSPECTION",
    "PRESS": "CORRECTION",
}


def save(scenario: Scenario, path: str | Path) -> None:
    data = {
        "blocks": [
            {
                "id": block.id,
                "type": normalize_block_type(block.type),
                "x": block.x,
                "y": block.y,
                "process_time_per_ea": block.process_time_per_ea,
                "concurrent_capacity": block.concurrent_capacity,
                "product_name": block.product_name,
                "material_name": block.material_name,
                "input_quantity": block.input_quantity,
                "input_time": block.input_time,
                "transport_capacity": block.transport_capacity,
                "transport_time": block.transport_time,
                "custom_name": block.custom_name,
            }
            for block in scenario.blocks
        ],
        "connections": [
            {
                "id": connection.id,
                "from": connection.from_block,
                "to": connection.to_block,
            }
            for connection in scenario.connections
        ],
    }

    Path(path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load(path: str | Path) -> Scenario:
    data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))

    scenario = Scenario(
        blocks=[
            ProcessBlock(
                id=block_data["id"],
                type=normalize_block_type(block_data["type"]),
                x=block_data["x"],
                y=block_data["y"],
                process_time_per_ea=block_data["process_time_per_ea"],
                concurrent_capacity=block_data["concurrent_capacity"],
                product_name=block_data.get("product_name", "제품"),
                material_name=block_data.get("material_name", "원자재"),
                input_quantity=block_data.get("input_quantity", 10),
                input_time=block_data.get("input_time", 0.0),
                transport_capacity=block_data.get("transport_capacity", 1),
                transport_time=block_data.get("transport_time", 1.0),
                custom_name=block_data.get("custom_name", ""),
            )
            for block_data in data.get("blocks", [])
        ],
        connections=[
            ProcessConnection(
                id=connection_data["id"],
                from_block=connection_data["from"],
                to_block=connection_data["to"],
            )
            for connection_data in data.get("connections", [])
        ],
    )
    return scenario


def normalize_block_type(block_type: str) -> str:
    return LEGACY_BLOCK_TYPE_MAP.get(block_type, block_type)
