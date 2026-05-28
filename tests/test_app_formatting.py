from app import BLOCK_TYPES, format_flow_diagram
from engine.models import ProcessConnection


def test_branch_join_flow_diagram_uses_actual_connections():
    connections = [
        ProcessConnection(id=1, from_block=1, to_block=2),
        ProcessConnection(id=2, from_block=1, to_block=3),
        ProcessConnection(id=3, from_block=2, to_block=4),
        ProcessConnection(id=4, from_block=3, to_block=4),
    ]

    diagram = format_flow_diagram(
        process_flow=[1, 2, 3, 4],
        connections=connections,
        block_label=lambda block_id: f"B{block_id}",
    )

    assert diagram.splitlines() == [
        "B1 -> B2",
        "B1 -> B3",
        "B2 -> B4",
        "B3 -> B4",
    ]
    assert "B1 -> B2 -> B3 -> B4" not in diagram


def test_flow_diagram_lists_independent_blocks_without_fake_edges():
    diagram = format_flow_diagram(
        process_flow=[1, 2],
        connections=[],
        block_label=lambda block_id: f"B{block_id}",
    )

    assert diagram.splitlines() == ["B1", "B2"]


def test_block_taxonomy_uses_approved_order_and_labels():
    assert list(BLOCK_TYPES) == [
        "INPUT",
        "WORK_WAITING",
        "PREPROCESS",
        "BENDING",
        "DRAWING",
        "CUTTING",
        "HEAT",
        "CORRECTION",
        "POSTPROCESS",
        "INSPECTION",
        "PACKING",
        "HOIST",
        "FREE",
    ]
    assert [block_type.label for block_type in BLOCK_TYPES.values()] == [
        "원자재 투입",
        "작업대기",
        "전처리",
        "구부",
        "인발",
        "절단",
        "열처리",
        "교정",
        "후처리",
        "검사",
        "포장",
        "호이스트",
        "Free Block",
    ]

    old_labels = {"적재", "프레스 교정기", "자동진직도 측정기", "절단기", "열처리기"}
    assert old_labels.isdisjoint({block_type.label for block_type in BLOCK_TYPES.values()})


def test_new_process_taxonomy_defaults_do_not_change_special_blocks():
    new_normal_types = [
        "WORK_WAITING",
        "PREPROCESS",
        "BENDING",
        "DRAWING",
        "CORRECTION",
        "POSTPROCESS",
        "INSPECTION",
        "PACKING",
    ]
    for block_type in new_normal_types:
        assert BLOCK_TYPES[block_type].default_process_time_per_ea == 30.0
        assert BLOCK_TYPES[block_type].default_concurrent_capacity == 1

    assert BLOCK_TYPES["CUTTING"].default_process_time_per_ea == 45
    assert BLOCK_TYPES["HEAT"].default_process_time_per_ea == 120
    assert BLOCK_TYPES["HOIST"].default_transport_capacity == 4
    assert BLOCK_TYPES["HOIST"].default_transport_time == 3.0
    assert BLOCK_TYPES["INPUT"].default_input_quantity == 10
    assert BLOCK_TYPES["FREE"].default_process_time_per_ea == 30
