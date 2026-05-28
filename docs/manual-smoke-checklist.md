# Manual Smoke Checklist: FactorySimulation

Updated: 2026-05-28

Use this checklist for manual tkinter verification after changes to `app.py`.

## Basic Editing

- Confirm the palette order is: 원자재 투입, 작업대기, 전처리, 구부, 인발, 절단, 열처리, 교정, 후처리, 검사, 포장, 호이스트, Free Block.
- Confirm old visible labels such as 적재, 절단기, 열처리기, 프레스 교정기, and 자동진직도 측정기 do not appear in the palette.
- Add a 원자재 투입 block, edit product name, material name, input quantity, and input time.
- Confirm normal process and 호이스트 block settings do not show a product-name field.
- Add new normal process blocks and confirm they default to 30 min/EA and 1EA concurrent quantity, except retained 절단 and 열처리 defaults.
- Add a 호이스트 block, edit transport quantity and move time.
- Add, move, connect, delete blocks and connections.
- Confirm connecting into an INPUT block shows a Korean error message.

## Visual Refresh

- Confirm the main shell keeps the same three-pane layout and window sizing while using the calmer dashboard styling.
- Confirm palette buttons use the approved Korean labels and emojis with consistent spacing and readable text.
- Confirm the canvas background, grid, block outlines, connection lines, delete badges, waiting highlights, processing highlights, and bottleneck badges are easy to read.
- Confirm the right result panel is easier to scan and still keeps the same summary, timeline, analysis, current-time, and selected-bundle content.
- Confirm block setting dialogs have only minor spacing/readability cleanup and the same fields, validation, save, cancel, and Free Block naming behavior.

## Simulation Scenarios

- INPUT-only: total input quantity and final output quantity match the INPUT quantity.
- Multiple INPUT blocks may reuse the same product name and the same product/material pair.
- Serial: INPUT 10EA, input time 0, process 1 min/EA and 1EA capacity, second process 1 min/EA and 1EA capacity produces 20 min total time.
- Input time: same serial scenario with input time 5 min produces 25 min total time.
- Hoist: 10EA with 4EA per move and 3 min per move reports 9 min and 3 moves.
- Branch: downstream weights 4 and 1 split 10EA into 8EA and 2EA without duplicating quantity.
- Join: multiple INPUT lines entering one process keep bundle-level FIFO and do not merge bundles.
- Material grouping: A, B, later A entering a process is handled A, A, B.
- Hoist FIFO exception: the same A, B, later A sequence through HOIST is handled by arrival FIFO.

## Results

- Summary shows total input quantity, final output quantity, total time, unique product-label count, product-label input EA, and product-label output EA.
- Block results show processed EA quantity, processed bundle count, unique product-label count, and unique material count.
- HOIST results show move count.
- Detailed analysis shows product name, material name, bundle quantity, start time, and completion time.
- Branch/join bundle details keep product and material labels without merging same-label bundles.
- Branch/join flow is shown from actual connections, not as a fake linear chain.

## Animation

- Run a simulation and confirm the central diagram shows playback controls above the canvas.
- Click play, pause, stop, and confirm stop returns the playhead to 0.0 minutes.
- Change speed between 0.5x, 1x, 2x, and 5x and confirm playhead movement changes.
- Drag the time slider and confirm playback pauses and the diagram updates to the selected time.
- Confirm bundle tokens show product/material labels and EA quantity.
- Confirm waiting bundles stack outside the block and processing bundles appear inside the block.
- Confirm a block with waiting bundles gets a subtle warning outline.
- Confirm the bottleneck block shows a small badge and is further emphasized when processing.
- Click a bundle token and confirm the right panel shows selected bundle details.
- Click empty canvas space or press Escape and confirm bundle selection clears.
- Use a large multi-input scenario and confirm compact token mode appears instead of overcrowding the canvas.
- Move a block after simulation and confirm the result remains available, but playback stops.
- Add/delete blocks, add/delete connections, edit parameters, load, or clear and confirm the result is marked as needing rerun.
- Save a scenario and confirm playback/result state does not change.

## Persistence

- Save a scenario containing INPUT product/material labels, process, and HOIST blocks.
- Load the saved scenario and confirm all new fields are preserved.
- Load an older scenario JSON with no `product_name` and confirm INPUT uses default product name `제품`.
- Load an older scenario JSON using `STORAGE`, `STRAIGHTNESS`, and `PRESS`; confirm they become `WORK_WAITING`, `INSPECTION`, and `CORRECTION`.
- Save that normalized legacy scenario again and confirm the JSON contains only the new type IDs.
- Run simulation after load and compare the result with the pre-save run.
