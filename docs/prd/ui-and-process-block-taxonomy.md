# PRD: UI Visual Refresh and Process Block Taxonomy

Updated: 2026-05-28

Status: ready-for-agent

GitHub references:

- PRD issue: #32
- Implementation issue: #33 - Implement new process block taxonomy and palette defaults
- Implementation issue: #34 - Normalize legacy scenario block types on load and save
- Implementation issue: #35 - Refresh main dashboard shell and block palette visuals
- Implementation issue: #36 - Refresh diagram canvas, block, connection, and token visuals
- Implementation issue: #37 - Refresh results panel, dialogs, and manual smoke checklist

## Problem Statement

FactorySimulation is already a functional Tkinter desktop simulator for process flow modeling, bundle-level quantity flow, hoist transport, bottleneck analysis, and playback visualization. However, the current interface still feels utilitarian and uneven. The user wants the program to look cleaner and more polished without changing any functional behavior, interaction model, simulation math, or existing animation behavior.

The process block palette also no longer matches the user's preferred factory vocabulary. The simulator currently has a small set of legacy block types, including some names that should be replaced by the user's real process language. The user needs a richer process block taxonomy that includes raw material input, hoist transport, multiple normal process stages, work waiting, and a free-form block, while keeping existing scenario files usable.

From the user's perspective, this work should make the application feel like a calm production/process dashboard and make the palette read like the actual factory flow. It should not surprise users by changing what a click does, how a scenario simulates, how connections work, how playback works, or how existing results are calculated.

## Solution

Refresh the main Tkinter UI visually while preserving the current layout and behavior. Keep the existing three-pane structure: block palette on the left, process diagram and playback controls in the center, and simulation results on the right. Keep the default window size and minimum window size. Adjust only the visual presentation: spacing, padding, color palette, borders, canvas tone, block styling, connection line styling, text readability, panel polish, and light dialog spacing.

Replace the visible process block palette with the user's new taxonomy and order:

1. 원자재 투입
2. 작업대기
3. 전처리
4. 구부
5. 인발
6. 절단
7. 열처리
8. 교정
9. 후처리
10. 검사
11. 포장
12. 호이스트
13. Free Block

Keep `원자재 투입` and `호이스트` as special block types because the simulation engine treats input and hoist differently from normal process blocks. Keep `호이스트` exposed in the palette, but do not add a new rule that every scenario must contain a hoist. In this PRD, "must exist" means the block remains available as a core modeling tool, not that simulation validation rejects scenarios without one.

All new normal process blocks should behave like existing normal process blocks: they have processing time per EA and concurrent processing quantity. They do not introduce new simulation semantics. Existing retained blocks keep their current defaults, while newly introduced normal process blocks share a conservative default of `30 min/EA` and `1 EA` concurrent capacity.

Legacy scenario files should remain loadable. When loading older files, old type IDs should be normalized to the new internal type IDs. After loading and saving again, the scenario should be saved using only the new type IDs.

## User Stories

1. As a process simulator user, I want the main app to look cleaner, so that I can work with process diagrams for longer without visual fatigue.
2. As a process simulator user, I want the current three-pane layout to stay the same, so that I do not need to relearn where tools and results are located.
3. As a process simulator user, I want the left palette to use my real factory process names, so that creating a scenario feels natural.
4. As a process simulator user, I want 원자재 투입 to remain available, so that I can define the material and product quantities entering the process.
5. As a process simulator user, I want 호이스트 to remain available, so that I can model transport capacity and transport time.
6. As a process simulator user, I want 호이스트 to remain a special block, so that it continues to use transport quantity and movement time instead of normal processing fields.
7. As a process simulator user, I want scenarios without a hoist to continue running when otherwise valid, so that the visual taxonomy change does not alter validation rules.
8. As a process simulator user, I want 작업대기 in the palette, so that I can represent waiting or staging between process steps.
9. As a process simulator user, I want 전처리 in the palette, so that upstream preparation can be modeled explicitly.
10. As a process simulator user, I want 후처리 in the palette, so that downstream finishing can be modeled explicitly.
11. As a process simulator user, I want 구부 in the palette, so that bending/forming work can be represented directly.
12. As a process simulator user, I want 인발 in the palette, so that drawing work can be represented directly.
13. As a process simulator user, I want 절단 to remain available, so that existing cutting flows still map to the new palette.
14. As a process simulator user, I want 열처리 to remain available, so that heat treatment flows still map to the new palette.
15. As a process simulator user, I want 교정 in the palette, so that straightening/correction work can be represented with the preferred term.
16. As a process simulator user, I want 검사 in the palette, so that inspection steps can be represented directly.
17. As a process simulator user, I want 포장 in the palette, so that the end of a production flow can be represented directly.
18. As a process simulator user, I want Free Block to remain available, so that I can still name a custom process when the fixed taxonomy is not enough.
19. As a process simulator user, I want the block palette ordered by likely process flow, so that I can scan it from input toward completion.
20. As a process simulator user, I want the palette order to place 호이스트 near the end as a reusable transport/special block, so that it is available without interrupting the main process sequence.
21. As a process simulator user, I want the visible labels to match exactly the new process names, so that old terms like 적재, 프레스 교정기, and 자동진직도 측정기 no longer appear in the main UI.
22. As a process simulator user, I want existing scenario files with old block types to load correctly, so that previous work is not lost.
23. As a process simulator user, I want old 적재 blocks to become 작업대기 on load, so that legacy waiting/staging scenarios follow the new vocabulary.
24. As a process simulator user, I want old 자동진직도 측정기 blocks to become 검사 on load, so that legacy inspection-like scenarios follow the new vocabulary.
25. As a process simulator user, I want old 프레스 교정기 blocks to become 교정 on load, so that legacy correction scenarios follow the new vocabulary.
26. As a process simulator user, I want normalized legacy scenarios to save using the new type names, so that future files stay clean.
27. As a process simulator user, I want 신규 일반 공정 blocks to default to `30 min/EA` and `1 EA`, so that newly added process types behave predictably.
28. As a process simulator user, I want retained blocks to keep their existing defaults, so that current expectations for 절단, 열처리, 호이스트, 원자재 투입, and Free Block do not shift.
29. As a process simulator user, I want emojis to remain in the UI, so that the app keeps its current visual recognizability.
30. As a process simulator user, I want emoji placement and sizing to look more consistent, so that retaining emojis does not make the refreshed UI feel uneven.
31. As a process simulator user, I want block colors grouped by process family but still individually distinct, so that the diagram is readable without becoming noisy.
32. As a process simulator user, I want the UI tone to feel like a calm factory/process dashboard, so that it looks work-focused rather than decorative.
33. As a process simulator user, I want central canvas styling to become cleaner, so that blocks, connections, playback tokens, waiting states, and bottleneck emphasis are easier to read.
34. As a process simulator user, I want the existing playback controls to stay functionally identical, so that play, pause, stop, speed, and time slider behavior do not change.
35. As a process simulator user, I want the right result panel to become more readable, so that current time state, selected bundle details, summary, timeline, and analysis are easier to scan.
36. As a process simulator user, I want block setting dialogs to receive only minor visual cleanup, so that data entry remains familiar.
37. As a process simulator user, I want connection creation, deletion, dragging, double-click editing, right-click menus, and Escape behavior to remain unchanged, so that existing workflows continue working.
38. As a process simulator user, I want simulation results to remain mathematically identical for equivalent scenarios, so that the UI refresh does not affect trust in the engine.
39. As a process simulator user, I want animation results to remain behaviorally identical, so that token state, compact mode, stale state, and bottleneck highlighting continue working.
40. As a maintainer, I want the block taxonomy to be defined in one clear registry, so that adding or adjusting visible process names later is straightforward.
41. As a maintainer, I want legacy type mapping to be isolated, so that old-file compatibility is testable and does not spread across UI code.
42. As a maintainer, I want tests to cover legacy type normalization, so that file compatibility does not regress silently.
43. As a maintainer, I want existing simulation tests to continue passing, so that new block labels do not accidentally change engine semantics.
44. As a maintainer, I want the manual smoke checklist updated minimally, so that manual verification matches the new palette and visual refresh.

## Implementation Decisions

- The UI refresh is visual only. It may adjust style, spacing, colors, borders, canvas background, block rendering, connection rendering, panel padding, and text readability. It must not change feature behavior.
- The existing main window size, minimum window size, and three-pane layout remain unchanged.
- The left palette remains the place for adding blocks. The center remains the process diagram and playback area. The right panel remains the simulation result area.
- The block setting dialogs receive minimal spacing/readability cleanup only. Their fields, validation, and save/cancel behavior remain unchanged.
- Emojis remain part of the visible UI. They should be aligned and sized consistently enough to fit the calmer dashboard tone.
- Block colors should be grouped by process family while keeping individual block distinction. Special blocks, shaping/processing blocks, thermal/correction/inspection blocks, and finishing/flow blocks should read as related groups without becoming a one-color UI.
- The visible block labels are exactly: 원자재 투입, 작업대기, 전처리, 구부, 인발, 절단, 열처리, 교정, 후처리, 검사, 포장, 호이스트, Free Block.
- The palette order follows the expected process flow: 원자재 투입, 작업대기, 전처리, 구부, 인발, 절단, 열처리, 교정, 후처리, 검사, 포장, 호이스트, Free Block.
- The internal type IDs are:
  - `INPUT` for 원자재 투입
  - `WORK_WAITING` for 작업대기
  - `PREPROCESS` for 전처리
  - `BENDING` for 구부
  - `DRAWING` for 인발
  - `CUTTING` for 절단
  - `HEAT` for 열처리
  - `CORRECTION` for 교정
  - `POSTPROCESS` for 후처리
  - `INSPECTION` for 검사
  - `PACKING` for 포장
  - `HOIST` for 호이스트
  - `FREE` for Free Block
- Legacy type IDs are normalized on load:
  - `STORAGE` becomes `WORK_WAITING`
  - `STRAIGHTNESS` becomes `INSPECTION`
  - `PRESS` becomes `CORRECTION`
- After a legacy scenario is loaded and saved, the saved file should contain the normalized new type IDs.
- `INPUT` and `HOIST` remain the only special simulation categories. New process block types are normal process blocks.
- No new validation rule should require a hoist to exist in every scenario.
- New normal process types default to `30 min/EA` and concurrent capacity `1 EA`.
- Retained block defaults remain unchanged for 원자재 투입, 호이스트, 절단, 열처리, and Free Block.
- Free Block keeps its custom-name behavior.
- Scenario save/load should preserve all existing data fields and normalize only the block type where needed.
- The simulation engine should not receive new math for the new normal process types. Equivalent graphs should produce equivalent outputs.
- The animation controller should not change behavior. Token states, selected token details, compact token mode, stale result handling, playback speeds, and bottleneck highlighting remain as-is.
- The result panel content should not be restructured functionally. It may receive readability and spacing improvements.
- The manual smoke checklist should be updated to mention the new block palette, legacy load normalization, and visual-only UI refresh checks.

## Testing Decisions

- Good automated tests should verify external behavior: what scenario files load into, what type IDs are saved, what defaults are applied, and whether existing simulation behavior remains stable. Tests should not lock onto incidental widget internals, exact pixel positions, or private helper implementation details unless there is already a focused pattern for that behavior.
- Scenario persistence should be tested for legacy type normalization. A saved legacy scenario using old type IDs should load as the new internal type IDs.
- Scenario round-trip behavior should be tested so that a normalized scenario saves with new type IDs.
- Block taxonomy/default behavior should be tested where practical without requiring full manual GUI automation.
- Existing engine tests should remain passing to prove that new normal process types do not require new simulation math.
- Existing animation tests should remain passing to prove that the visual refresh and block taxonomy change do not alter playback state behavior.
- Manual verification remains important for Tkinter appearance. The manual smoke checklist should cover palette order, visible labels, emoji rendering, visual polish, playback controls, result panel readability, and unchanged interaction behavior.
- Existing tests for scenario model validation, simulation flow, product/material tracking, hoist behavior, and animation compact mode are relevant prior art.

## Out of Scope

- Changing simulation math.
- Adding required-hoist validation.
- Changing connection rules.
- Changing the graph validation model.
- Adding a new output block.
- Changing bundle routing, split behavior, join behavior, material grouping, or hoist FIFO behavior.
- Changing playback timing, token state logic, compact token aggregation, or stale-result semantics.
- Changing save/load schema beyond type normalization for legacy block IDs.
- Replacing Tkinter with another UI framework.
- Rebuilding the layout into new screens, new tabs, or a different navigation structure.
- Adding auto-layout, snap-to-grid, minimap, zoom, pan, or diagram routing.
- Adding new analytics, charts, exports, reporting, or printing.
- Adding product-specific process times, BOM, yield, defect, labor, inventory, or resource constraints.
- Removing emojis.
- Translating the whole app or adding a localization system.
- Changing archived PRDs or handoff documents.

## Further Notes

- This PRD intentionally separates visual polish from functional behavior. If a proposed UI change affects what users can do or how simulation results are computed, it belongs in a separate PRD.
- The highest-risk part of the block taxonomy change is old-file compatibility. The type normalizer should be small, explicit, and tested.
- The UI should feel calmer and more professional, but not like a marketing page. This is an operational desktop tool for repeated use.
- Because this is Tkinter, exact visual fidelity may vary by Windows font/theme. The target is consistent readability and spacing, not pixel-perfect styling.
- The implementation should leave archived documents alone and update only the active manual smoke checklist as needed.
