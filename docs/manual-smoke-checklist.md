# Manual Smoke Checklist: Bundle/Hoist Phase A

Updated: 2026-05-27

Use this checklist for manual tkinter verification after changes to `app.py`.

## Basic Editing

- Add an INPUT block, edit material name, input quantity, and input time.
- Add a process block, edit process time and concurrent processing quantity.
- Add a HOIST block, edit transport quantity and move time.
- Add, move, connect, delete blocks and connections.
- Confirm connecting into an INPUT block shows a Korean error message.

## Simulation Scenarios

- INPUT-only: total input quantity and final output quantity match the INPUT quantity.
- Serial: INPUT 10EA, input time 0, process 1 min/EA and 1EA capacity, second process 1 min/EA and 1EA capacity produces 20 min total time.
- Input time: same serial scenario with input time 5 min produces 25 min total time.
- Hoist: 10EA with 4EA per move and 3 min per move reports 9 min and 3 moves.
- Branch: downstream weights 4 and 1 split 10EA into 8EA and 2EA without duplicating quantity.
- Join: multiple INPUT lines entering one process keep bundle-level FIFO and do not merge bundles.
- Material grouping: A, B, later A entering a process is handled A, A, B.
- Hoist FIFO exception: the same A, B, later A sequence through HOIST is handled by arrival FIFO.

## Results

- Summary shows total input quantity, final output quantity, and total time.
- Block results show processed EA quantity and processed bundle count.
- HOIST results show move count.
- Detailed analysis shows material name, bundle quantity, start time, and completion time.
- Branch/join flow is shown from actual connections, not as a fake linear chain.

## Persistence

- Save a scenario containing INPUT, process, and HOIST blocks.
- Load the saved scenario and confirm all new fields are preserved.
- Run simulation after load and compare the result with the pre-save run.
