from app import AnimationController, BundleTokenState, CanvasView
from engine.models import ProcessBlock, ProcessConnection
from engine.simulation import simulate


def input_block(
    block_id: int,
    product_name: str = "P",
    material_name: str = "A",
    quantity: int = 1,
    input_time: float = 0,
) -> ProcessBlock:
    return ProcessBlock(
        id=block_id,
        type="INPUT",
        x=0,
        y=0,
        product_name=product_name,
        material_name=material_name,
        input_quantity=quantity,
        input_time=input_time,
    )


def process_block(block_id: int, process_time: float = 1) -> ProcessBlock:
    return ProcessBlock(
        id=block_id,
        type="CUTTING",
        x=0,
        y=0,
        process_time_per_ea=process_time,
        concurrent_capacity=1,
    )


def test_token_states_distinguish_waiting_processing_and_complete():
    blocks = [
        input_block(1, material_name="A"),
        input_block(2, material_name="A"),
        process_block(3, process_time=1),
    ]
    connections = [
        ProcessConnection(id=1, from_block=1, to_block=3),
        ProcessConnection(id=2, from_block=2, to_block=3),
    ]
    result = simulate(blocks, connections)
    controller = AnimationController()
    controller.set_connections(connections)
    controller.set_result(result)

    controller.set_time(0.5, result.total_time)
    tokens = controller.token_states(result)

    assert [token.state for token in tokens] == ["processing", "waiting"]
    assert tokens[0].progress == 0.5

    controller.set_time(result.total_time, result.total_time)
    tokens = controller.token_states(result)

    assert [token.state for token in tokens] == ["complete", "complete"]


def test_playback_speed_targets_about_30_seconds_at_1x():
    controller = AnimationController()
    result = simulate([input_block(1, quantity=30, input_time=30)], [])
    controller.set_result(result)

    assert controller.playback_minutes_per_second(result.total_time) == 1.0

    controller.state.speed_multiplier = 2.0

    assert controller.playback_minutes_per_second(result.total_time) == 2.0


def test_stale_and_layout_changes_are_distinct():
    controller = AnimationController()
    result = simulate([input_block(1)], [])
    controller.set_result(result)

    controller.mark_layout_changed()

    assert controller.state.is_stale is False
    assert controller.state.is_playing is False

    controller.mark_structure_changed()

    assert controller.state.is_stale is True


def test_product_color_is_stable_for_same_product():
    controller = AnimationController()

    assert controller.product_color("제품A") == controller.product_color("제품A")


def test_display_tokens_compacts_large_active_sets_by_block_and_state():
    blocks = [input_block(index, material_name="A") for index in range(1, 27)]
    blocks.append(process_block(27, process_time=1))
    connections = [
        ProcessConnection(id=index, from_block=index, to_block=27)
        for index in range(1, 27)
    ]
    result = simulate(blocks, connections)
    controller = AnimationController()
    controller.set_connections(connections)
    controller.set_result(result)
    controller.set_time(0.5, result.total_time)

    tokens = controller.display_tokens(result)

    assert controller.state.is_compact is True
    assert sum(token.bundle_count for token in tokens) == 26
    assert any(token.is_aggregate and token.state == "waiting" for token in tokens)


def test_canvas_token_drawing_does_not_depend_on_connection_delete_coordinates():
    class FakeCanvas:
        def __init__(self):
            self.calls = []

        def create_rectangle(self, *args, **kwargs):
            self.calls.append(("rectangle", args, kwargs))

        def create_text(self, *args, **kwargs):
            self.calls.append(("text", args, kwargs))

    class FakeController:
        def __init__(self):
            self.animation = AnimationController()

    view = CanvasView.__new__(CanvasView)
    view.canvas = FakeCanvas()
    view.controller = FakeController()
    token = BundleTokenState(
        token_id="bundle:1",
        bundle_id=1,
        block_id=1,
        product_name="P",
        material_name="A",
        quantity=10,
        state="processing",
        arrival_time=0,
        start_time=0,
        completion_time=10,
        progress=0.5,
        source_token_ids=("bundle:1",),
    )

    view._draw_token(token, 10, 20, selected_id=None)

    assert [call[0] for call in view.canvas.calls] == ["rectangle", "text"]


def test_processing_token_position_stays_outside_block_bounds():
    view = CanvasView.__new__(CanvasView)
    block = ProcessBlock(
        id=1,
        type="CUTTING",
        x=100,
        y=200,
        width=150,
        height=80,
    )
    token = BundleTokenState(
        token_id="bundle:1",
        bundle_id=1,
        block_id=1,
        product_name="P",
        material_name="A",
        quantity=10,
        state="processing",
        arrival_time=0,
        start_time=0,
        completion_time=10,
        progress=0.5,
        source_token_ids=("bundle:1",),
    )

    x, y = view._token_position(token, block, index=0)
    token_width, token_height = view._token_size(token)

    token_is_left = x + token_width <= block.x
    token_is_right = x >= block.x + block.width
    token_is_above = y + token_height <= block.y
    token_is_below = y >= block.y + block.height

    assert token_is_left or token_is_right or token_is_above or token_is_below
