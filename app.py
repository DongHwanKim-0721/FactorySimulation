from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from engine.models import ProcessBlock, ProcessConnection, Scenario
from engine.scenario_io import load as load_scenario_file
from engine.scenario_io import save as save_scenario_file
from engine.simulation import BlockResult, BundleRecord, SimulationResult, simulate


@dataclass(frozen=True)
class BlockType:
    label: str
    color: str
    icon: str
    default_process_time_per_ea: float = 30.0
    default_concurrent_capacity: int = 1
    default_input_quantity: int = 10
    default_input_time: float = 0.0
    default_transport_capacity: int = 4
    default_transport_time: float = 3.0


BLOCK_TYPES: dict[str, BlockType] = {
    "INPUT": BlockType("원자재 투입", "#2563eb", "📥", default_input_quantity=10),
    "WORK_WAITING": BlockType("작업대기", "#64748b", "⏳"),
    "PREPROCESS": BlockType("전처리", "#0f766e", "🧰"),
    "BENDING": BlockType("구부", "#d97706", "🔧"),
    "DRAWING": BlockType("인발", "#7c3aed", "🧵"),
    "CUTTING": BlockType("절단", "#f59e0b", "✂️", 45),
    "HEAT": BlockType("열처리", "#dc2626", "🔥", 120),
    "CORRECTION": BlockType("교정", "#db2777", "⚙️"),
    "POSTPROCESS": BlockType("후처리", "#0891b2", "🧼"),
    "INSPECTION": BlockType("검사", "#4f46e5", "🔍"),
    "PACKING": BlockType("포장", "#16a34a", "📦"),
    "HOIST": BlockType("호이스트", "#0f766e", "🏗️", default_transport_capacity=4),
    "FREE": BlockType("Free Block", "#6b7280", "📋", 30),
}


def format_flow_diagram(
    process_flow: list[int],
    connections: list[ProcessConnection],
    block_label: Callable[[int], str],
    block_icon: Callable[[int], str] | None = None,
) -> str:
    flow_ids = set(process_flow)
    icon_for = block_icon or (lambda _block_id: "")

    def label(block_id: int) -> str:
        return f"{icon_for(block_id)}{block_label(block_id)}"

    visible_connections = [
        connection
        for connection in connections
        if connection.from_block in flow_ids and connection.to_block in flow_ids
    ]
    if visible_connections:
        return "\n".join(
            f"{label(connection.from_block)} -> {label(connection.to_block)}"
            for connection in visible_connections
        )

    return "\n".join(label(block_id) for block_id in process_flow)


TOKEN_STATE_LABELS = {
    "not_arrived": "도착 전",
    "waiting": "대기 중",
    "processing": "처리 중",
    "complete": "완료",
}

PRODUCT_TOKEN_COLORS = [
    "#2563eb",
    "#16a34a",
    "#d97706",
    "#7c3aed",
    "#dc2626",
    "#0891b2",
    "#be185d",
    "#4d7c0f",
]


@dataclass
class PlaybackState:
    current_time: float = 0.0
    is_playing: bool = False
    speed_multiplier: float = 1.0
    selected_token_id: str | None = None
    is_stale: bool = False
    is_compact: bool = False


@dataclass(frozen=True)
class BundleTokenState:
    token_id: str
    bundle_id: int | None
    block_id: int
    product_name: str
    material_name: str
    quantity: int
    state: str
    arrival_time: float
    start_time: float
    completion_time: float
    progress: float
    bundle_count: int = 1
    is_aggregate: bool = False
    source_token_ids: tuple[str, ...] = ()


class AnimationController:
    target_playback_seconds = 30.0
    compact_threshold = 24

    def __init__(self) -> None:
        self.state = PlaybackState()

    def set_result(self, result: SimulationResult) -> None:
        self.state.current_time = min(self.state.current_time, result.total_time)
        self.state.is_playing = False
        self.state.selected_token_id = None
        self.state.is_stale = False
        self.state.is_compact = False

    def mark_structure_changed(self) -> None:
        self.state.is_playing = False
        self.state.is_stale = True

    def mark_layout_changed(self) -> None:
        self.state.is_playing = False

    def clear(self) -> None:
        self.state = PlaybackState()

    def set_time(self, current_time: float, total_time: float) -> None:
        self.state.current_time = max(0.0, min(float(current_time), total_time))

    def playback_minutes_per_second(self, total_time: float) -> float:
        if total_time <= 0:
            return 0.0
        return (total_time / self.target_playback_seconds) * self.state.speed_multiplier

    def advance(self, total_time: float, elapsed_ms: int) -> bool:
        step = self.playback_minutes_per_second(total_time) * (elapsed_ms / 1000)
        self.set_time(self.state.current_time + step, total_time)
        if self.state.current_time >= total_time:
            self.state.is_playing = False
            return True
        return False

    def token_states(
        self,
        result: SimulationResult,
        include_not_arrived: bool = False,
    ) -> list[BundleTokenState]:
        records_by_bundle = self._records_by_bundle(result)
        sink_ids = self._sink_block_ids(result)
        tokens: list[BundleTokenState] = []

        for bundle_id in sorted(records_by_bundle):
            records = records_by_bundle[bundle_id]
            token = self._token_for_bundle(records, sink_ids)
            if include_not_arrived or token.state != "not_arrived":
                tokens.append(token)

        return tokens

    def display_tokens(self, result: SimulationResult) -> list[BundleTokenState]:
        active_tokens = self.token_states(result)
        if len(active_tokens) <= self.compact_threshold:
            self.state.is_compact = False
            return active_tokens

        self.state.is_compact = True
        return self._aggregate_tokens(active_tokens)

    def current_summary(self, tokens: list[BundleTokenState]) -> dict[str, int]:
        summary = {state: 0 for state in TOKEN_STATE_LABELS}
        for token in tokens:
            summary[token.state] = summary.get(token.state, 0) + token.bundle_count
        return summary

    def selected_token(
        self,
        result: SimulationResult,
    ) -> BundleTokenState | None:
        selected_id = self.state.selected_token_id
        if not selected_id:
            return None

        display_tokens = self.display_tokens(result)
        for token in display_tokens:
            if token.token_id == selected_id:
                return token

        for token in self.token_states(result, include_not_arrived=True):
            if token.token_id == selected_id:
                return token
        return None

    def product_color(self, product_name: str) -> str:
        index = sum(ord(char) for char in product_name) % len(PRODUCT_TOKEN_COLORS)
        return PRODUCT_TOKEN_COLORS[index]

    def _records_by_bundle(
        self,
        result: SimulationResult,
    ) -> dict[int, list[BundleRecord]]:
        records_by_bundle: dict[int, list[BundleRecord]] = {}
        for block_result in result.timeline:
            for bundle in block_result.bundles:
                records_by_bundle.setdefault(bundle.bundle_id, []).append(bundle)

        for records in records_by_bundle.values():
            records.sort(
                key=lambda bundle: (
                    bundle.arrival_time,
                    bundle.start_time,
                    bundle.completion_time,
                    bundle.block_id,
                )
            )
        return records_by_bundle

    def _sink_block_ids(self, result: SimulationResult) -> set[int]:
        block_ids = {item.block_id for item in result.timeline}
        parent_ids = {
            connection.from_block
            for connection in self._active_connections
            if connection.from_block in block_ids
        }
        return block_ids - parent_ids

    @property
    def _active_connections(self) -> list[ProcessConnection]:
        return getattr(self, "connections", [])

    def set_connections(self, connections: list[ProcessConnection]) -> None:
        self.connections = connections

    def _token_for_bundle(
        self,
        records: list[BundleRecord],
        sink_ids: set[int],
    ) -> BundleTokenState:
        current_time = self.state.current_time
        first = records[0]

        if current_time < first.arrival_time:
            return self._build_token(first, "not_arrived", 0.0)

        for record in records:
            if current_time < record.arrival_time:
                return self._build_token(record, "not_arrived", 0.0)
            if current_time < record.start_time:
                return self._build_token(record, "waiting", 0.0)
            if current_time < record.completion_time:
                progress = self._progress(current_time, record.start_time, record.completion_time)
                return self._build_token(record, "processing", progress)

        last = records[-1]
        if last.block_id in sink_ids:
            return self._build_token(last, "complete", 1.0)
        return self._build_token(last, "not_arrived", 0.0)

    def _build_token(
        self,
        record: BundleRecord,
        state: str,
        progress: float,
    ) -> BundleTokenState:
        return BundleTokenState(
            token_id=f"bundle:{record.bundle_id}",
            bundle_id=record.bundle_id,
            block_id=record.block_id,
            product_name=record.product_name,
            material_name=record.material_name,
            quantity=record.quantity,
            state=state,
            arrival_time=record.arrival_time,
            start_time=record.start_time,
            completion_time=record.completion_time,
            progress=progress,
            source_token_ids=(f"bundle:{record.bundle_id}",),
        )

    def _aggregate_tokens(
        self,
        tokens: list[BundleTokenState],
    ) -> list[BundleTokenState]:
        grouped: dict[tuple[int, str, str, str], list[BundleTokenState]] = {}
        for token in tokens:
            key = (
                token.block_id,
                token.state,
                token.product_name,
                token.material_name,
            )
            grouped.setdefault(key, []).append(token)

        aggregates: list[BundleTokenState] = []
        for key, group in sorted(grouped.items()):
            block_id, state, product_name, material_name = key
            source_ids = tuple(token.token_id for token in group)
            aggregates.append(
                BundleTokenState(
                    token_id=(
                        f"aggregate:{block_id}:{state}:"
                        f"{product_name}:{material_name}"
                    ),
                    bundle_id=None,
                    block_id=block_id,
                    product_name=product_name,
                    material_name=material_name,
                    quantity=sum(token.quantity for token in group),
                    state=state,
                    arrival_time=min(token.arrival_time for token in group),
                    start_time=min(token.start_time for token in group),
                    completion_time=max(token.completion_time for token in group),
                    progress=sum(token.progress for token in group) / len(group),
                    bundle_count=sum(token.bundle_count for token in group),
                    is_aggregate=True,
                    source_token_ids=source_ids,
                )
            )
        return aggregates

    def _progress(self, current_time: float, start_time: float, completion_time: float) -> float:
        if completion_time <= start_time:
            return 1.0
        return max(0.0, min(1.0, (current_time - start_time) / (completion_time - start_time)))


class App:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("공정 시뮬레이션 프로그램 v1.2")
        self.root.geometry("1600x900")
        self.root.minsize(1200, 700)
        self.root.configure(bg="#e8edf3")

        style = ttk.Style()
        style.theme_use("clam")
        self._configure_style(style)

        self.scenario = Scenario()
        self.last_result: SimulationResult | None = None
        self.animation = AnimationController()
        self._animation_after_id: str | None = None
        self.connection_start_id: int | None = None
        self.status_var = tk.StringVar(value="준비 완료")

        self._create_widgets()
        self.root.bind("<Escape>", self.handle_escape)

    def _configure_style(self, style: ttk.Style) -> None:
        style.configure(
            ".",
            background="#e8edf3",
            foreground="#1f2937",
            font=("Arial", 10),
        )
        style.configure("App.TFrame", background="#e8edf3")
        style.configure("Toolbar.TFrame", background="#1f2937", relief=tk.FLAT)
        style.configure(
            "ToolbarTitle.TLabel",
            background="#1f2937",
            foreground="#f8fafc",
            font=("Arial", 16, "bold"),
        )
        style.configure(
            "Toolbar.TButton",
            background="#334155",
            foreground="#f8fafc",
            bordercolor="#475569",
            focusthickness=1,
            focuscolor="#93c5fd",
            padding=(10, 6),
        )
        style.map(
            "Toolbar.TButton",
            background=[("active", "#475569"), ("pressed", "#0f172a")],
            foreground=[("disabled", "#94a3b8")],
        )
        style.configure(
            "Panel.TLabelframe",
            background="#f8fafc",
            bordercolor="#cbd5e1",
            relief=tk.GROOVE,
        )
        style.configure(
            "Panel.TLabelframe.Label",
            background="#e8edf3",
            foreground="#0f172a",
            font=("Arial", 11, "bold"),
        )
        style.configure("Panel.TFrame", background="#f8fafc")
        style.configure("Panel.TLabel", background="#f8fafc", foreground="#334155")
        style.configure("Playback.TFrame", background="#f8fafc")
        style.configure("Status.TLabel", background="#dbe3ec", foreground="#334155")
        style.configure("TNotebook", background="#f8fafc", borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            padding=(12, 6),
            background="#e2e8f0",
            foreground="#475569",
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#ffffff"), ("active", "#f1f5f9")],
            foreground=[("selected", "#0f172a")],
        )

    def _create_widgets(self) -> None:
        main_frame = ttk.Frame(self.root, style="App.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(main_frame, style="Toolbar.TFrame", padding=(12, 8))
        toolbar.pack(fill=tk.X)
        ttk.Label(
            toolbar,
            text="공정 시뮬레이션 프로그램 v1.2",
            style="ToolbarTitle.TLabel",
        ).pack(side=tk.LEFT, padx=10)

        button_frame = ttk.Frame(toolbar, style="Toolbar.TFrame")
        button_frame.pack(side=tk.RIGHT, padx=10)
        for label, command in (
            ("시뮬레이션 실행", self.run_simulation),
            ("저장", self.save_scenario),
            ("불러오기", self.load_scenario),
            ("초기화", self.clear_all),
        ):
            ttk.Button(
                button_frame,
                text=label,
                command=command,
                style="Toolbar.TButton",
            ).pack(side=tk.LEFT, padx=3)

        content_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        content_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(content_paned, width=240, style="App.TFrame")
        center_frame = ttk.Frame(content_paned, style="App.TFrame")
        right_frame = ttk.Frame(content_paned, width=420, style="App.TFrame")
        content_paned.add(left_frame, weight=0)
        content_paned.add(center_frame, weight=3)
        content_paned.add(right_frame, weight=1)

        self.palette_view = PaletteView(left_frame, self)
        self.canvas_view = CanvasView(center_frame, self)
        self.result_view = ResultView(right_frame, self)

        status_bar = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            anchor=tk.W,
            style="Status.TLabel",
            padding=(10, 4),
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def run(self) -> None:
        self.root.mainloop()

    def add_block(self, block_type: str) -> None:
        block_type_info = BLOCK_TYPES[block_type]
        custom_name = ""
        if block_type == "FREE":
            custom_name = self.prompt_free_block_name()
            if not custom_name:
                return

        block = self.scenario.add_block(
            block_type=block_type,
            x=150,
            y=100 + len(self.scenario.blocks) * 100,
            process_time_per_ea=block_type_info.default_process_time_per_ea,
            concurrent_capacity=block_type_info.default_concurrent_capacity,
            input_quantity=block_type_info.default_input_quantity,
            input_time=block_type_info.default_input_time,
            transport_capacity=block_type_info.default_transport_capacity,
            transport_time=block_type_info.default_transport_time,
            custom_name=custom_name,
        )
        self.mark_structure_changed("블록이 변경되어 시뮬레이션 재실행이 필요합니다.")
        self.canvas_view.redraw()
        self.status_var.set(f"{self.block_display_name(block)} 블록이 추가되었습니다.")

    def prompt_free_block_name(self) -> str:
        dialog = tk.Toplevel(self.root)
        dialog.title("Free Block 이름 입력")
        dialog.geometry("400x180")
        dialog.configure(bg="#f8fafc")
        dialog.transient(self.root)
        dialog.grab_set()

        result = {"name": ""}
        name_var = tk.StringVar(value="사용자 정의 블록")

        ttk.Label(
            dialog,
            text="블록 이름을 입력하세요:",
            font=("Arial", 11, "bold"),
        ).pack(pady=20)
        entry = ttk.Entry(dialog, textvariable=name_var, width=30, font=("Arial", 10))
        entry.pack(pady=10)
        entry.focus()

        def save_name() -> None:
            result["name"] = name_var.get().strip()
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="확인", command=save_name).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="취소", command=dialog.destroy).pack(
            side=tk.LEFT, padx=5
        )
        entry.bind("<Return>", lambda _event: save_name())

        dialog.wait_window()
        return result["name"]

    def edit_block_parameters(self, block_id: int) -> None:
        block = self.find_block(block_id)
        if not block:
            return

        block_type_info = BLOCK_TYPES[block.type]
        dialog = tk.Toplevel(self.root)
        dialog.title(f"{self.block_display_name(block)} 설정")
        dialog.geometry("460x380")
        dialog.configure(bg="#f8fafc")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text=f"{block_type_info.icon} {self.block_display_name(block)}",
            font=("Arial", 14, "bold"),
        ).pack(fill=tk.X, padx=20, pady=12)

        form_frame = ttk.Frame(dialog, padding=(22, 14), style="Panel.TFrame")
        form_frame.pack(fill=tk.BOTH, expand=True)
        form_frame.columnconfigure(1, weight=1)

        row = 0
        name_var = tk.StringVar(value=block.custom_name)
        if block.type == "FREE":
            ttk.Label(form_frame, text="블록 이름:").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=name_var, width=22).grid(
                row=row, column=1, sticky="ew", pady=5
            )
            row += 1

        product_name_var = tk.StringVar(value=block.product_name)
        material_name_var = tk.StringVar(value=block.material_name)
        input_quantity_var = tk.IntVar(value=block.input_quantity)
        input_time_var = tk.DoubleVar(value=block.input_time)
        process_time_var = tk.DoubleVar(value=block.process_time_per_ea)
        concurrent_capacity_var = tk.IntVar(value=block.concurrent_capacity)
        transport_capacity_var = tk.IntVar(value=block.transport_capacity)
        transport_time_var = tk.DoubleVar(value=block.transport_time)

        if block.type == "INPUT":
            ttk.Label(form_frame, text="제품명:").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=product_name_var, width=22).grid(
                row=row, column=1, sticky="ew", pady=5
            )
            row += 1

            ttk.Label(form_frame, text="원자재명:").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=material_name_var, width=22).grid(
                row=row, column=1, sticky="ew", pady=5
            )
            row += 1

            ttk.Label(form_frame, text="투입 원자재 수(EA):").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=input_quantity_var, width=22).grid(
                row=row, column=1, sticky="ew", pady=5
            )
            row += 1

            ttk.Label(form_frame, text="투입 시간(분):").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=input_time_var, width=22).grid(
                row=row, column=1, sticky="ew", pady=5
            )
        elif block.type == "HOIST":
            ttk.Label(form_frame, text="1회 운반 수량(EA):").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=transport_capacity_var, width=22).grid(
                row=row, column=1, sticky="ew", pady=5
            )
            row += 1

            ttk.Label(form_frame, text="1회 이동 시간(분):").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=transport_time_var, width=22).grid(
                row=row, column=1, sticky="ew", pady=5
            )
        else:
            ttk.Label(form_frame, text="처리 시간(분/EA):").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=process_time_var, width=22).grid(
                row=row, column=1, sticky="ew", pady=5
            )
            row += 1

            ttk.Label(form_frame, text="동시 가공 수량(EA):").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=concurrent_capacity_var, width=22).grid(
                row=row, column=1, sticky="ew", pady=5
            )

        def save_params() -> None:
            try:
                input_quantity = int(input_quantity_var.get())
                input_time = float(input_time_var.get())
                process_time = float(process_time_var.get())
                concurrent_capacity = int(concurrent_capacity_var.get())
                transport_capacity = int(transport_capacity_var.get())
                transport_time = float(transport_time_var.get())
            except tk.TclError:
                messagebox.showerror(
                    "입력 오류",
                    "수량과 시간은 숫자로 입력해주세요.",
                )
                return

            if block.type == "INPUT":
                product_name = product_name_var.get().strip()
                material_name = material_name_var.get().strip()
                if not product_name:
                    messagebox.showerror(
                        "입력 오류",
                        "제품명을 입력해주세요.",
                    )
                    return
                if not material_name:
                    messagebox.showerror("입력 오류", "원자재명을 입력해주세요.")
                    return
                if input_quantity < 0 or input_time < 0:
                    messagebox.showerror(
                        "입력 오류",
                        "투입 원자재 수와 투입 시간은 0 이상이어야 합니다.",
                    )
                    return
                block.product_name = product_name
                block.material_name = material_name
                block.input_quantity = input_quantity
                block.input_time = input_time
            elif block.type == "HOIST":
                if transport_capacity <= 0 or transport_time <= 0:
                    messagebox.showerror(
                        "입력 오류",
                        "1회 운반 수량은 1 이상, 1회 이동 시간은 0보다 커야 합니다.",
                    )
                    return
                block.transport_capacity = transport_capacity
                block.transport_time = transport_time
            elif process_time <= 0 or concurrent_capacity <= 0:
                messagebox.showerror(
                    "입력 오류",
                    "처리 시간은 0보다 커야 하고 동시 가공 수량은 1 이상이어야 합니다.",
                )
                return
            else:
                block.process_time_per_ea = process_time
                block.concurrent_capacity = concurrent_capacity

            if block.type == "FREE":
                block.custom_name = name_var.get().strip()
            self.mark_structure_changed("파라미터가 변경되어 시뮬레이션 재실행이 필요합니다.")
            self.canvas_view.redraw()
            dialog.destroy()
            self.status_var.set("파라미터가 저장되었습니다.")

        button_frame = ttk.Frame(dialog, padding=10)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="저장", command=save_params).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="취소", command=dialog.destroy).pack(
            side=tk.LEFT, padx=5
        )

    def move_block(self, block_id: int, dx: float, dy: float) -> None:
        block = self.find_block(block_id)
        if not block:
            return
        block.x += dx
        block.y += dy
        self.animation.mark_layout_changed()
        self.canvas_view.redraw()
        self.canvas_view.update_playback_controls()

    def start_or_finish_connection(self, block_id: int) -> None:
        block = self.find_block(block_id)
        if not block:
            return

        if self.connection_start_id is None:
            self.connection_start_id = block_id
            self.canvas_view.show_connection_start(block_id)
            self.status_var.set(
                f"{self.block_display_name(block)}에서 연결을 시작합니다. 대상 블록을 Shift+클릭하세요."
            )
            return

        from_block = self.find_block(self.connection_start_id)
        if not from_block:
            self.end_connection_mode()
            return

        try:
            self.scenario.add_connection(self.connection_start_id, block_id)
        except ValueError as exc:
            messagebox.showwarning("연결 오류", f"연결을 만들 수 없습니다:\n{exc}")
            self.status_var.set("연결을 생성하지 못했습니다.")
        else:
            self.mark_structure_changed("연결이 변경되어 시뮬레이션 재실행이 필요합니다.")
            self.canvas_view.redraw()
            self.status_var.set("연결이 완료되었습니다.")
        finally:
            self.end_connection_mode()

    def cancel_connection(self, _event: object | None = None) -> None:
        if self.connection_start_id is None:
            return
        start_block = self.find_block(self.connection_start_id)
        start_name = self.block_display_name(start_block) if start_block else "선택 블록"
        self.end_connection_mode()
        self.status_var.set(f"{start_name}에서 시작한 연결이 취소되었습니다.")

    def handle_escape(self, event: object | None = None) -> None:
        if self.connection_start_id is not None:
            self.cancel_connection(event)
            return
        self.select_animation_token(None)

    def end_connection_mode(self) -> None:
        self.connection_start_id = None
        self.canvas_view.end_connection_mode()

    def delete_block(self, block_id: int) -> None:
        block = self.find_block(block_id)
        if not block:
            return
        if not messagebox.askyesno(
            "삭제 확인",
            f"{self.block_display_name(block)} 블록을 삭제하시겠습니까?",
        ):
            return
        self.scenario.delete_block(block_id)
        self.mark_structure_changed("블록이 삭제되어 시뮬레이션 재실행이 필요합니다.")
        self.canvas_view.redraw()
        self.status_var.set("블록이 삭제되었습니다.")

    def delete_connection(self, connection_id: int) -> None:
        connection = self.find_connection(connection_id)
        if not connection:
            return

        from_block = self.find_block(connection.from_block)
        to_block = self.find_block(connection.to_block)
        from_name = self.block_display_name(from_block) if from_block else "Unknown"
        to_name = self.block_display_name(to_block) if to_block else "Unknown"

        if not messagebox.askyesno(
            "연결 삭제",
            f"{from_name} → {to_name}\n이 연결을 삭제하시겠습니까?",
        ):
            return
        self.scenario.delete_connection(connection_id)
        self.mark_structure_changed("연결이 삭제되어 시뮬레이션 재실행이 필요합니다.")
        self.canvas_view.redraw()
        self.status_var.set("연결이 삭제되었습니다.")

    def run_simulation(self) -> None:
        if not self.scenario.blocks:
            messagebox.showwarning("경고", "공정 블록을 추가해주세요.")
            return

        try:
            result = simulate(
                self.scenario.blocks,
                self.scenario.connections,
            )
        except ValueError as exc:
            messagebox.showerror("시뮬레이션 오류", str(exc))
            return

        if not result.timeline:
            messagebox.showerror("오류", "시뮬레이션 결과가 없습니다.")
            return

        self.last_result = result
        self.animation.set_connections(self.scenario.connections)
        self.animation.set_result(result)
        self.result_view.display(result)
        self.refresh_animation()
        self.status_var.set(f"시뮬레이션 완료 - 총 리드타임: {result.total_time:.1f}분")

    def save_scenario(self) -> None:
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
            title="시나리오 저장",
        )
        if not filename:
            return

        try:
            save_scenario_file(self.scenario, filename)
        except OSError as exc:
            messagebox.showerror("저장 오류", f"저장 중 오류가 발생했습니다:\n{exc}")
            return

        messagebox.showinfo("저장 완료", f"시나리오가 저장되었습니다:\n{filename}")
        self.status_var.set(f"시나리오 저장됨: {filename}")

    def load_scenario(self) -> None:
        filename = filedialog.askopenfilename(
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
            title="시나리오 불러오기",
        )
        if not filename:
            return

        try:
            self.scenario = load_scenario_file(filename)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            messagebox.showerror("불러오기 오류", f"불러오기 중 오류가 발생했습니다:\n{exc}")
            return

        self.last_result = None
        self.connection_start_id = None
        self.animation.clear()
        self.canvas_view.redraw()
        self.result_view.clear()
        messagebox.showinfo("불러오기 완료", "시나리오가 불러와졌습니다.")
        self.mark_structure_changed("불러온 시나리오는 시뮬레이션 실행이 필요합니다.")
        self.status_var.set(f"시나리오 불러옴: {filename}")

    def clear_all(self) -> None:
        if not messagebox.askyesno("초기화 확인", "모든 블록과 연결을 삭제하시겠습니까?"):
            return
        self.scenario = Scenario()
        self.last_result = None
        self.connection_start_id = None
        self.animation.clear()
        self.canvas_view.redraw()
        self.result_view.clear()
        self.mark_structure_changed("초기화되어 시뮬레이션 실행이 필요합니다.")
        self.status_var.set("초기화 완료")

    def mark_structure_changed(self, message: str) -> None:
        if self.last_result is not None:
            self.animation.mark_structure_changed()
        else:
            self.animation.state.is_playing = False
            self.animation.state.is_stale = True
        self.stop_animation_timer()
        if hasattr(self, "canvas_view"):
            self.canvas_view.update_playback_controls()
        if hasattr(self, "result_view"):
            self.result_view.set_stale(self.animation.state.is_stale)
        if message:
            self.status_var.set(message)

    def toggle_playback(self) -> None:
        if self.last_result is None:
            self.status_var.set("먼저 시뮬레이션을 실행해주세요.")
            return
        if self.animation.state.is_stale:
            self.status_var.set("결과가 오래되었습니다. 시뮬레이션을 다시 실행해주세요.")
            return

        if self.animation.state.is_playing:
            self.animation.state.is_playing = False
            self.stop_animation_timer()
        else:
            if self.animation.state.current_time >= self.last_result.total_time:
                self.animation.set_time(0, self.last_result.total_time)
            self.animation.state.is_playing = True
            self.schedule_animation_tick()
        self.refresh_animation()

    def stop_playback(self) -> None:
        self.animation.state.is_playing = False
        self.stop_animation_timer()
        total_time = self.last_result.total_time if self.last_result else 0
        self.animation.set_time(0, total_time)
        self.refresh_animation()

    def seek_playhead(self, current_time: float) -> None:
        if self.last_result is None:
            return
        self.animation.state.is_playing = False
        self.stop_animation_timer()
        self.animation.set_time(current_time, self.last_result.total_time)
        self.refresh_animation()

    def set_playback_speed(self, speed_text: str) -> None:
        try:
            self.animation.state.speed_multiplier = float(speed_text.rstrip("x"))
        except ValueError:
            self.animation.state.speed_multiplier = 1.0
        self.canvas_view.update_playback_controls()

    def schedule_animation_tick(self) -> None:
        self.stop_animation_timer()
        self._animation_after_id = self.root.after(100, self.animation_tick)

    def stop_animation_timer(self) -> None:
        if self._animation_after_id is None:
            return
        self.root.after_cancel(self._animation_after_id)
        self._animation_after_id = None

    def animation_tick(self) -> None:
        self._animation_after_id = None
        if not self.last_result or not self.animation.state.is_playing:
            return
        self.animation.advance(self.last_result.total_time, elapsed_ms=100)
        self.refresh_animation()
        if self.animation.state.is_playing:
            self.schedule_animation_tick()

    def select_animation_token(self, token_id: str | None) -> None:
        self.animation.state.selected_token_id = token_id
        self.refresh_animation()

    def refresh_animation(self) -> None:
        if hasattr(self, "canvas_view"):
            self.canvas_view.redraw()
            self.canvas_view.update_playback_controls()
        if hasattr(self, "result_view"):
            self.result_view.update_animation_panel()

    def animation_display_tokens(self) -> list[BundleTokenState]:
        if self.last_result is None or self.animation.state.is_stale:
            self.animation.state.is_compact = False
            return []
        self.animation.set_connections(self.scenario.connections)
        return self.animation.display_tokens(self.last_result)

    def block_display_name(self, block: ProcessBlock | None) -> str:
        if block is None:
            return "Unknown"
        if block.type == "INPUT" and (block.product_name or block.material_name):
            return (
                f"{BLOCK_TYPES[block.type].label}"
                f"({block.product_name}/{block.material_name})"
            )
        if block.type == "FREE" and block.custom_name:
            return block.custom_name
        return BLOCK_TYPES[block.type].label

    def block_result_display_name(self, result: BlockResult) -> str:
        return self.block_display_name(self.find_block(result.block_id))

    def find_block(self, block_id: int) -> ProcessBlock | None:
        return next((block for block in self.scenario.blocks if block.id == block_id), None)

    def find_connection(self, connection_id: int) -> ProcessConnection | None:
        return next(
            (
                connection
                for connection in self.scenario.connections
                if connection.id == connection_id
            ),
            None,
        )

    def bottleneck_reason(self, result: SimulationResult) -> str:
        block = self.find_block(result.bottleneck_id) if result.bottleneck_id else None
        if not block:
            return "병목 없음"
        if block.type == "HOIST":
            return (
                f"이론 처리율 {result.bottleneck_throughput:.3f} EA/분 "
                f"(1회 운반 수량 {block.transport_capacity} EA / "
                f"1회 이동 시간 {block.transport_time:g}분)"
            )
        return (
            f"이론 처리율 {result.bottleneck_throughput:.3f} EA/분 "
            f"(동시 가공 수량 {block.concurrent_capacity} EA / "
            f"처리 시간 {block.process_time_per_ea:g}분/EA)"
        )

    def bottleneck_impact(self, result: SimulationResult) -> str:
        if result.bottleneck_id is None:
            return "없음"
        total_waiting = sum(
            sum(item.waiting_times)
            for item in result.timeline
            if item.block_id != result.bottleneck_id
        )
        return f"다른 공정의 총 대기시간: {total_waiting:.1f}분"


class PaletteView:
    def __init__(self, parent: tk.Widget, controller: App) -> None:
        self.controller = controller
        self.frame = ttk.LabelFrame(
            parent,
            text="공정 블록 팔레트",
            padding=12,
            style="Panel.TLabelframe",
        )
        self.frame.pack(fill=tk.BOTH, expand=True, padx=(10, 5), pady=10)
        self._create_widgets()

    def _create_widgets(self) -> None:
        canvas = tk.Canvas(self.frame, width=250, bg="#f8fafc", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="Panel.TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for key, block_type in BLOCK_TYPES.items():
            if key == "INPUT":
                detail = f"{block_type.default_input_quantity} EA"
            elif key == "HOIST":
                detail = (
                    f"{block_type.default_transport_capacity} EA/"
                    f"{block_type.default_transport_time:g}분"
                )
            else:
                detail = f"{block_type.default_process_time_per_ea:g}분/EA"
            button = tk.Button(
                scrollable_frame,
                text=f"{block_type.icon} {block_type.label}\n({detail})",
                bg=block_type.color,
                fg=self._text_color_for_button(key),
                font=("Arial", 10, "bold"),
                activebackground=block_type.color,
                activeforeground=self._text_color_for_button(key),
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                cursor="hand2",
                anchor=tk.W,
                justify=tk.LEFT,
                padx=14,
                command=lambda block_key=key: self.controller.add_block(block_key),
            )
            button.pack(fill=tk.X, pady=4, ipady=9)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _text_color_for_button(self, block_type: str) -> str:
        if block_type in {"BENDING", "CUTTING", "PACKING"}:
            return "#111827"
        return "white"


class CanvasView:
    def __init__(self, parent: tk.Widget, controller: App) -> None:
        self.controller = controller
        self.drag_block_id: int | None = None
        self.drag_x = 0.0
        self.drag_y = 0.0
        self.current_tokens: list[BundleTokenState] = []
        self._updating_controls = False

        self.frame = ttk.LabelFrame(
            parent,
            text="공정 다이어그램",
            padding=8,
            style="Panel.TLabelframe",
        )
        self.frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=10)

        self.playback_frame = ttk.Frame(self.frame, style="Playback.TFrame")
        self.playback_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.playback_frame.grid_columnconfigure(4, weight=1)

        self.play_button = ttk.Button(
            self.playback_frame,
            text="재생",
            width=8,
            command=self.controller.toggle_playback,
        )
        self.play_button.grid(row=0, column=0, padx=(0, 4))
        ttk.Button(
            self.playback_frame,
            text="정지",
            width=8,
            command=self.controller.stop_playback,
        ).grid(row=0, column=1, padx=(0, 8))

        self.speed_var = tk.StringVar(value="1x")
        speed_box = ttk.Combobox(
            self.playback_frame,
            textvariable=self.speed_var,
            values=("0.5x", "1x", "2x", "5x"),
            width=6,
            state="readonly",
        )
        speed_box.grid(row=0, column=2, padx=(0, 8))
        speed_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.controller.set_playback_speed(self.speed_var.get()),
        )

        self.time_var = tk.StringVar(value="0.0 / 0.0분")
        ttk.Label(self.playback_frame, textvariable=self.time_var, width=18).grid(
            row=0,
            column=3,
            padx=(0, 8),
        )

        self.time_scale_var = tk.DoubleVar(value=0)
        self.time_scale = ttk.Scale(
            self.playback_frame,
            from_=0,
            to=1,
            orient=tk.HORIZONTAL,
            variable=self.time_scale_var,
            command=self._on_seek,
        )
        self.time_scale.grid(row=0, column=4, sticky="ew", padx=(0, 8))

        self.state_var = tk.StringVar(value="시뮬레이션 전")
        ttk.Label(
            self.playback_frame,
            textvariable=self.state_var,
            foreground="#b45309",
            width=16,
        ).grid(row=0, column=5)

        self.canvas = tk.Canvas(
            self.frame,
            bg="#eef3f8",
            cursor="cross",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
        )
        h_scroll = ttk.Scrollbar(self.frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scroll = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
            scrollregion=(0, 0, 2000, 2000),
        )

        self.canvas.grid(row=1, column=0, sticky="nsew")
        h_scroll.grid(row=2, column=0, sticky="ew")
        v_scroll.grid(row=1, column=1, sticky="ns")
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)

    def redraw(self) -> None:
        self.canvas.delete("all")
        self.current_tokens = self.controller.animation_display_tokens()
        self.draw_grid()
        for connection in self.controller.scenario.connections:
            self.draw_connection(connection)
        for block in self.controller.scenario.blocks:
            self.draw_block(block)
        self.draw_animation_tokens()

    def draw_block(self, block: ProcessBlock) -> None:
        block_type = BLOCK_TYPES[block.type]
        display_name = self.controller.block_display_name(block)
        text_color = self._text_color_for_block(block.type)
        block_tokens = [token for token in self.current_tokens if token.block_id == block.id]
        has_waiting = any(token.state == "waiting" for token in block_tokens)
        processing = [token for token in block_tokens if token.state == "processing"]
        is_bottleneck = (
            self.controller.last_result is not None
            and self.controller.last_result.bottleneck_id == block.id
        )
        outline = "#ffffff"
        outline_width = 3
        if has_waiting:
            outline = "#f59e0b"
            outline_width = 4
        if processing:
            outline = "#22c55e"
            outline_width = 4
        if is_bottleneck:
            outline = "#dc2626"
            outline_width = 5

        self.canvas.create_rectangle(
            block.x + 4,
            block.y + 4,
            block.x + block.width + 4,
            block.y + block.height + 4,
            fill="#cbd5e1",
            outline="",
            tags=f"block_{block.id}",
        )
        self.canvas.create_rectangle(
            block.x,
            block.y,
            block.x + block.width,
            block.y + block.height,
            fill=block_type.color,
            outline=outline,
            width=outline_width,
            tags=f"block_{block.id}",
        )
        if processing:
            progress = max(token.progress for token in processing)
            self.canvas.create_rectangle(
                block.x + 6,
                block.y + block.height - 10,
                block.x + block.width - 6,
                block.y + block.height - 4,
                fill="#dbeafe",
                outline="",
                tags=f"block_{block.id}",
            )
            self.canvas.create_rectangle(
                block.x + 6,
                block.y + block.height - 10,
                block.x + 6 + (block.width - 12) * progress,
                block.y + block.height - 4,
                fill="#22c55e",
                outline="",
                tags=f"block_{block.id}",
            )
        self.canvas.create_text(
            block.x + 20,
            block.y + 20,
            text=block_type.icon,
            font=("Arial", 20),
            fill=text_color,
            tags=f"block_{block.id}",
        )
        if is_bottleneck:
            self.canvas.create_rectangle(
                block.x + block.width - 50,
                block.y - 12,
                block.x + block.width + 2,
                block.y + 10,
                fill="#dc2626",
                outline="white",
                width=1,
                tags=f"block_{block.id}",
            )
            self.canvas.create_text(
                block.x + block.width - 24,
                block.y - 1,
                text="병목",
                font=("Arial", 8, "bold"),
                fill="white",
                tags=f"block_{block.id}",
            )
        self.canvas.create_text(
            block.x + 75,
            block.y + 20,
            text=display_name,
            font=("Arial", 9, "bold"),
            fill=text_color,
            width=88,
            tags=f"block_{block.id}",
        )
        line1, line2 = self._block_metric_lines(block)
        self.canvas.create_text(
            block.x + 75,
            block.y + 45,
            text=line1,
            font=("Arial", 8),
            fill=text_color,
            tags=f"block_{block.id}",
        )
        self.canvas.create_text(
            block.x + 75,
            block.y + 60,
            text=line2,
            font=("Arial", 8),
            fill=text_color,
            tags=f"block_{block.id}",
        )

    def _text_color_for_block(self, block_type: str) -> str:
        if block_type in {"BENDING", "CUTTING", "PACKING"}:
            return "#111827"
        return "white"

    def _block_metric_lines(self, block: ProcessBlock) -> tuple[str, str]:
        if block.type == "INPUT":
            return (
                f"수량: {block.input_quantity} EA",
                f"투입: {block.input_time:g}분",
            )
        if block.type == "HOIST":
            return (
                f"운반: {block.transport_capacity} EA/회",
                f"이동: {block.transport_time:g}분/회",
            )
        return (
            f"처리: {block.process_time_per_ea:g}분/EA",
            f"동시: {block.concurrent_capacity} EA",
        )

    def draw_connection(self, connection: ProcessConnection) -> None:
        from_block = self.controller.find_block(connection.from_block)
        to_block = self.controller.find_block(connection.to_block)
        if not from_block or not to_block:
            return

        x1 = from_block.x + from_block.width + 5
        y1 = from_block.y + from_block.height / 2
        x2 = to_block.x - 10
        y2 = to_block.y + to_block.height / 2

        self.canvas.create_line(
            x1,
            y1,
            x2,
            y2,
            arrow=tk.LAST,
            fill="#475569",
            width=3,
            smooth=True,
            tags=f"conn_{connection.id}",
        )

        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        self.canvas.create_oval(
            mid_x - 8,
            mid_y - 8,
            mid_x + 8,
            mid_y + 8,
            fill="#ef4444",
            outline="white",
            width=2,
            tags=f"conn_{connection.id}_delete",
        )
        self.canvas.create_text(
            mid_x,
            mid_y,
            text="×",
            font=("Arial", 12, "bold"),
            fill="white",
            tags=f"conn_{connection.id}_delete",
        )

    def draw_grid(self) -> None:
        for position in range(0, 2001, 40):
            self.canvas.create_line(
                position,
                0,
                position,
                2000,
                fill="#e5e7eb",
                width=1,
                tags="grid",
            )
            self.canvas.create_line(
                0,
                position,
                2000,
                position,
                fill="#e5e7eb",
                width=1,
                tags="grid",
            )

    def draw_animation_tokens(self) -> None:
        stack_index: dict[tuple[int, str], int] = {}
        selected_id = self.controller.animation.state.selected_token_id
        for token in self.current_tokens:
            block = self.controller.find_block(token.block_id)
            if block is None:
                continue
            key = (token.block_id, token.state)
            index = stack_index.get(key, 0)
            stack_index[key] = index + 1
            x, y = self._token_position(token, block, index)
            self._draw_token(token, x, y, selected_id)

    def _token_position(
        self,
        token: BundleTokenState,
        block: ProcessBlock,
        index: int,
    ) -> tuple[float, float]:
        if token.state == "waiting":
            return block.x - 105, block.y + 8 + index * 30
        if token.state == "complete":
            return block.x + block.width + 12, block.y + 8 + index * 30
        return block.x + 12 + (index % 2) * 64, block.y + block.height - 38 + (index // 2) * 24

    def _draw_token(
        self,
        token: BundleTokenState,
        x: float,
        y: float,
        selected_id: str | None,
    ) -> None:
        width = 96 if token.is_aggregate else 58
        height = 24
        color = self.controller.animation.product_color(token.product_name)
        selected = token.token_id == selected_id
        outline = "#111827" if selected else "#ffffff"
        label = f"{token.product_name}/{token.material_name} {token.quantity}EA"
        if token.is_aggregate:
            label = f"{token.product_name}/{token.material_name} {token.quantity}EA · {token.bundle_count}개"

        self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill=color,
            outline=outline,
            width=3 if selected else 1,
            tags=("animation_token", f"token_{token.token_id}"),
        )
        self.canvas.create_text(
            x + width / 2,
            y + height / 2,
            text=label,
            font=("Arial", 7, "bold"),
            fill="white",
            width=width - 6,
            tags=("animation_token", f"token_{token.token_id}"),
        )

    def show_connection_start(self, block_id: int) -> None:
        block = self.controller.find_block(block_id)
        if not block:
            return
        self.canvas.config(cursor="tcross", bg="#fff7ed")
        self.canvas.delete("connection_highlight")
        self.canvas.create_rectangle(
            block.x - 5,
            block.y - 5,
            block.x + block.width + 5,
            block.y + block.height + 5,
            outline="#ef4444",
            width=4,
            dash=(5, 5),
            tags="connection_highlight",
        )

    def end_connection_mode(self) -> None:
        self.canvas.config(cursor="cross", bg="#eef3f8")
        self.canvas.delete("connection_highlight")

    def on_click(self, event: tk.Event) -> None:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        connection_id = self._connection_delete_at(x, y)
        if connection_id is not None:
            self.controller.delete_connection(connection_id)
            return

        token_id = self._animation_token_at(x, y)
        if token_id is not None:
            self.controller.select_animation_token(token_id)
            return

        block_id = self._block_at(x, y)
        if event.state & 0x0001:
            if block_id is not None:
                self.controller.start_or_finish_connection(block_id)
            return

        if block_id is not None:
            self.drag_block_id = block_id
            self.drag_x = x
            self.drag_y = y
            return

        self.drag_block_id = None
        self.controller.select_animation_token(None)

    def on_drag(self, event: tk.Event) -> None:
        if self.drag_block_id is None:
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        dx = x - self.drag_x
        dy = y - self.drag_y

        self.controller.move_block(self.drag_block_id, dx, dy)
        self.drag_x = x
        self.drag_y = y

    def on_release(self, _event: tk.Event) -> None:
        self.drag_block_id = None

    def on_double_click(self, event: tk.Event) -> None:
        block_id = self._block_at(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if block_id is not None:
            self.controller.edit_block_parameters(block_id)

    def on_right_click(self, event: tk.Event) -> None:
        block_id = self._block_at(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if block_id is None:
            return

        menu = tk.Menu(self.controller.root, tearoff=0)
        menu.add_command(
            label="설정",
            command=lambda: self.controller.edit_block_parameters(block_id),
        )
        menu.add_separator()
        menu.add_command(
            label="삭제",
            command=lambda: self.controller.delete_block(block_id),
        )
        menu.post(event.x_root, event.y_root)

    def on_mousewheel(self, event: tk.Event) -> None:
        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            self.canvas.yview_scroll(1, "units")

    def _block_at(self, x: float, y: float) -> int | None:
        clicked = self.canvas.find_overlapping(x, y, x, y)
        for item in clicked:
            for tag in self.canvas.gettags(item):
                if tag.startswith("block_"):
                    return int(tag.split("_")[1])
        return None

    def _connection_delete_at(self, x: float, y: float) -> int | None:
        clicked = self.canvas.find_overlapping(x, y, x, y)
        for item in clicked:
            for tag in self.canvas.gettags(item):
                if tag.startswith("conn_") and tag.endswith("_delete"):
                    return int(tag.split("_")[1])
        return None

    def _animation_token_at(self, x: float, y: float) -> str | None:
        clicked = self.canvas.find_overlapping(x, y, x, y)
        for item in clicked:
            for tag in self.canvas.gettags(item):
                if tag.startswith("token_"):
                    return tag.removeprefix("token_")
        return None

    def _on_seek(self, value: str) -> None:
        if self._updating_controls:
            return
        self.controller.seek_playhead(float(value))

    def update_playback_controls(self) -> None:
        result = self.controller.last_result
        state = self.controller.animation.state
        total_time = result.total_time if result else 0.0

        self._updating_controls = True
        self.time_scale.configure(to=max(total_time, 1.0))
        self.time_scale_var.set(state.current_time)
        self._updating_controls = False

        self.play_button.configure(text="일시정지" if state.is_playing else "재생")
        self.time_var.set(f"{state.current_time:.1f} / {total_time:.1f}분")
        if state.is_stale:
            self.state_var.set("재실행 필요")
        elif result and state.is_compact:
            self.state_var.set("축약 표시 중")
        elif result:
            self.state_var.set("결과 최신")
        else:
            self.state_var.set("시뮬레이션 전")


class ResultView:
    def __init__(self, parent: tk.Widget, controller: App) -> None:
        self.controller = controller
        self.frame = ttk.LabelFrame(
            parent,
            text="시뮬레이션 결과",
            padding=10,
            style="Panel.TLabelframe",
        )
        self.frame.pack(fill=tk.BOTH, expand=True, padx=(5, 10), pady=10)

        animation_frame = ttk.LabelFrame(
            self.frame,
            text="현재 시점",
            padding=8,
            style="Panel.TLabelframe",
        )
        animation_frame.pack(fill=tk.X, pady=(0, 8))
        self.animation_summary_var = tk.StringVar(value="시뮬레이션 전")
        self.animation_selection_var = tk.StringVar(value="선택 묶음 없음")
        ttk.Label(
            animation_frame,
            textvariable=self.animation_summary_var,
            justify=tk.LEFT,
            anchor=tk.W,
            style="Panel.TLabel",
        ).pack(fill=tk.X)
        ttk.Label(
            animation_frame,
            textvariable=self.animation_selection_var,
            justify=tk.LEFT,
            anchor=tk.W,
            style="Panel.TLabel",
        ).pack(fill=tk.X, pady=(4, 0))

        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        summary_frame = ttk.Frame(notebook, style="Panel.TFrame", padding=6)
        timeline_frame = ttk.Frame(notebook, style="Panel.TFrame", padding=6)
        analysis_frame = ttk.Frame(notebook, style="Panel.TFrame", padding=6)
        notebook.add(summary_frame, text="요약")
        notebook.add(timeline_frame, text="타임라인")
        notebook.add(analysis_frame, text="분석")

        self.summary_text = tk.Text(
            summary_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            bg="#ffffff",
            fg="#1f2937",
            relief=tk.FLAT,
            padx=8,
            pady=8,
            spacing1=2,
            spacing3=4,
            width=40,
            height=12,
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True)

        self.timeline_canvas = tk.Canvas(
            timeline_frame,
            bg="#ffffff",
            width=380,
            height=300,
            highlightthickness=1,
            highlightbackground="#e2e8f0",
        )
        timeline_scroll = ttk.Scrollbar(
            timeline_frame,
            orient=tk.VERTICAL,
            command=self.timeline_canvas.yview,
        )
        self.timeline_canvas.configure(yscrollcommand=timeline_scroll.set)
        self.timeline_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        timeline_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.analysis_text = tk.Text(
            analysis_frame,
            wrap=tk.WORD,
            font=("Arial", 9),
            bg="#ffffff",
            fg="#1f2937",
            relief=tk.FLAT,
            padx=8,
            pady=8,
            spacing1=2,
            spacing3=4,
            width=40,
            height=20,
        )
        analysis_scroll = ttk.Scrollbar(
            analysis_frame,
            orient=tk.VERTICAL,
            command=self.analysis_text.yview,
        )
        self.analysis_text.configure(yscrollcommand=analysis_scroll.set)
        self.analysis_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        analysis_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def clear(self) -> None:
        self.summary_text.delete(1.0, tk.END)
        self.timeline_canvas.delete("all")
        self.analysis_text.delete(1.0, tk.END)
        self.animation_summary_var.set("시뮬레이션 전")
        self.animation_selection_var.set("선택 묶음 없음")

    def display(self, result: SimulationResult) -> None:
        self.clear()
        bottleneck_name = self._bottleneck_name(result)
        bottleneck_reason = self.controller.bottleneck_reason(result)
        bottleneck_impact = self.controller.bottleneck_impact(result)

        self.summary_text.insert(tk.END, "=" * 40 + "\n")
        self.summary_text.insert(tk.END, "   묶음 기반 시뮬레이션 결과\n")
        self.summary_text.insert(tk.END, "=" * 40 + "\n\n")
        self.summary_text.insert(tk.END, f"총 소요 시간: {result.total_time:.1f}분\n")
        self.summary_text.insert(tk.END, f"전체 투입 수량: {result.total_input_quantity} EA\n")
        self.summary_text.insert(tk.END, f"최종 output 수량: {result.final_output_quantity} EA\n\n")
        self.summary_text.insert(
            tk.END,
            f"제품 추적 라벨 수: {result.unique_product_count}개\n",
        )
        self.summary_text.insert(
            tk.END,
            "제품 라벨별 투입 EA: "
            f"{self._format_product_quantities(result.input_quantity_by_product)}\n",
        )
        self.summary_text.insert(
            tk.END,
            "제품 라벨별 최종 output EA: "
            f"{self._format_product_quantities(result.final_output_quantity_by_product)}\n\n",
        )
        self.summary_text.insert(tk.END, f"병목 공정: {bottleneck_name}\n")
        self.summary_text.insert(tk.END, f"   이유: {bottleneck_reason}\n")
        self.summary_text.insert(tk.END, f"   영향: {bottleneck_impact}\n\n")
        self.summary_text.insert(tk.END, f"공정 수: {len(result.timeline)}개\n")

        avg_cycle = (
            result.total_time / result.final_output_quantity
            if result.final_output_quantity > 0
            else 0
        )
        self.summary_text.insert(tk.END, f"평균 소요 시간: {avg_cycle:.1f}분/EA\n")

        self._draw_timeline(result)
        self._write_analysis(result, bottleneck_name, bottleneck_reason, bottleneck_impact)
        self.update_animation_panel()

    def set_stale(self, is_stale: bool) -> None:
        if not is_stale:
            self.update_animation_panel()
            return
        if self.controller.last_result is None:
            self.animation_summary_var.set("시뮬레이션 실행이 필요합니다.")
        else:
            self.animation_summary_var.set("결과가 오래되었습니다. 시뮬레이션을 다시 실행해주세요.")

    def update_animation_panel(self) -> None:
        result = self.controller.last_result
        state = self.controller.animation.state
        if result is None:
            self.animation_summary_var.set(
                "시뮬레이션 실행이 필요합니다." if state.is_stale else "시뮬레이션 전"
            )
            self.animation_selection_var.set("선택 묶음 없음")
            return
        if state.is_stale:
            self.animation_summary_var.set(
                f"결과 오래됨 · 마지막 총 소요 시간 {result.total_time:.1f}분"
            )
            self.animation_selection_var.set("시뮬레이션 재실행 후 묶음 선택 가능")
            return

        tokens = self.controller.animation_display_tokens()
        summary = self.controller.animation.current_summary(tokens)
        summary_text = (
            f"현재 {state.current_time:.1f} / {result.total_time:.1f}분 · "
            f"대기 {summary.get('waiting', 0)}개 · "
            f"처리 {summary.get('processing', 0)}개 · "
            f"완료 {summary.get('complete', 0)}개"
        )
        if state.is_compact:
            summary_text += " · 축약 표시 중"
        self.animation_summary_var.set(summary_text)

        selected = self.controller.animation.selected_token(result)
        if selected is None:
            self.animation_selection_var.set("선택 묶음 없음")
            return

        block_name = self.controller.block_display_name(
            self.controller.find_block(selected.block_id)
        )
        state_label = TOKEN_STATE_LABELS.get(selected.state, selected.state)
        if selected.is_aggregate:
            self.animation_selection_var.set(
                f"선택 집계: {selected.product_name}/{selected.material_name} · "
                f"{selected.quantity}EA · 묶음 {selected.bundle_count}개 · "
                f"{state_label} · {block_name}"
            )
            return

        self.animation_selection_var.set(
            f"선택 묶음 #{selected.bundle_id}: "
            f"{selected.product_name}/{selected.material_name} {selected.quantity}EA · "
            f"{state_label} · {block_name} · "
            f"{selected.arrival_time:.1f}/{selected.start_time:.1f}/"
            f"{selected.completion_time:.1f}분"
        )

    def _format_product_quantities(self, quantities: dict[str, int]) -> str:
        if not quantities:
            return "없음"
        return ", ".join(
            f"{product_name} {quantity}EA"
            for product_name, quantity in sorted(quantities.items())
        )

    def _draw_timeline(self, result: SimulationResult) -> None:
        y_offset = 30
        self.timeline_canvas.create_text(
            10,
            y_offset,
            text="공정별 성능",
            anchor=tk.W,
            font=("Arial", 11, "bold"),
        )
        y_offset += 30

        finite_throughputs = [
            item.throughput
            for item in result.timeline
            if item.throughput != float("inf")
        ]
        max_throughput = max(finite_throughputs, default=0)
        for idx, item in enumerate(result.timeline):
            block = self.controller.find_block(item.block_id)
            block_type = BLOCK_TYPES[block.type] if block else BLOCK_TYPES["FREE"]
            item_name = self.controller.block_result_display_name(item)

            self.timeline_canvas.create_text(
                10,
                y_offset,
                text=f"{idx + 1}. {block_type.icon} {item_name}",
                anchor=tk.W,
                font=("Arial", 9, "bold"),
            )
            self.timeline_canvas.create_text(
                10,
                y_offset + 15,
                text=self._timeline_metric_text(item, block),
                anchor=tk.W,
                font=("Arial", 8),
                fill="gray",
            )
            if item.avg_waiting > 0.1:
                self.timeline_canvas.create_text(
                    10,
                    y_offset + 30,
                    text=f"평균 대기: {item.avg_waiting:.1f}분",
                    anchor=tk.W,
                    font=("Arial", 8),
                    fill="#ef4444",
                )
                route_y = y_offset + 45
            else:
                route_y = y_offset + 30

            self.timeline_canvas.create_text(
                10,
                route_y,
                text=self._route_text(item.block_id),
                anchor=tk.W,
                font=("Arial", 8),
                fill="#475569",
            )

            bar_x = 210
            bar_width = 120
            bar_height = 20
            bar_length = (
                (item.throughput / max_throughput) * bar_width
                if max_throughput and item.throughput != float("inf")
                else 0
            )
            is_bottleneck = item.block_id == result.bottleneck_id

            self.timeline_canvas.create_rectangle(
                bar_x,
                y_offset,
                bar_x + bar_width,
                y_offset + bar_height,
                fill="#e5e7eb",
                outline="#d1d5db",
            )
            self.timeline_canvas.create_rectangle(
                bar_x,
                y_offset,
                bar_x + bar_length,
                y_offset + bar_height,
                fill="#ef4444" if is_bottleneck else block_type.color,
                outline="white",
                width=2,
            )
            if is_bottleneck:
                self.timeline_canvas.create_text(
                    bar_x + bar_width + 10,
                    y_offset + bar_height / 2,
                    text="병목",
                    anchor=tk.W,
                    font=("Arial", 9, "bold"),
                    fill="red",
                )

            y_offset += 85 if item.avg_waiting > 0.1 else 70

        self.timeline_canvas.configure(scrollregion=self.timeline_canvas.bbox("all"))

    def _write_analysis(
        self,
        result: SimulationResult,
        bottleneck_name: str,
        bottleneck_reason: str,
        bottleneck_impact: str,
    ) -> None:
        self.analysis_text.insert(tk.END, "=" * 70 + "\n")
        self.analysis_text.insert(tk.END, "              묶음 기반 시뮬레이션 상세 분석\n")
        self.analysis_text.insert(tk.END, "=" * 70 + "\n\n")

        self.analysis_text.insert(tk.END, "공정 흐름\n")
        self.analysis_text.insert(tk.END, "-" * 70 + "\n")
        flow_diagram = format_flow_diagram(
            process_flow=result.process_flow,
            connections=self.controller.scenario.connections,
            block_label=self._block_name,
            block_icon=self._block_icon,
        )
        self.analysis_text.insert(tk.END, f"{flow_diagram}\n\n")

        self.analysis_text.insert(tk.END, "공정별 상세 분석\n")
        self.analysis_text.insert(tk.END, "-" * 70 + "\n")
        for idx, item in enumerate(result.timeline, 1):
            item_name = self.controller.block_result_display_name(item)
            self.analysis_text.insert(
                tk.END,
                f"\n{idx}. {self._block_icon(item.block_id)} {item_name}\n",
            )
            block = self.controller.find_block(item.block_id)
            self.analysis_text.insert(tk.END, "   기본 정보:\n")
            self._write_block_operation_details(item, block)
            self.analysis_text.insert(
                tk.END,
                f"   • 처리 제품 라벨 수: {item.unique_product_count}개\n",
            )
            self.analysis_text.insert(
                tk.END,
                f"   • 처리 원자재 수: {item.unique_material_count}개\n",
            )
            self.analysis_text.insert(tk.END, f"   • 실제 처리 수량: {item.total_processed} EA\n")
            self.analysis_text.insert(
                tk.END,
                f"   • 처리 묶음 수: {item.processed_bundle_count}개\n",
            )
            if item.transport_trips:
                self.analysis_text.insert(
                    tk.END,
                    f"   • 호이스트 이동 횟수: {item.transport_trips}회\n",
                )
            self.analysis_text.insert(tk.END, "\n   성능 지표:\n")
            self.analysis_text.insert(tk.END, f"   • 평균 대기 시간: {item.avg_waiting:.1f}분\n")

            if item.block_id == result.bottleneck_id:
                self.analysis_text.insert(tk.END, "\n   병목 공정\n")
                self.analysis_text.insert(tk.END, f"   → {bottleneck_reason}\n")
                self.analysis_text.insert(tk.END, "   → 전체 공정의 처리 속도를 제한하는 구간입니다.\n")

            if item.bundles:
                self.analysis_text.insert(tk.END, "\n   묶음별 타임라인 (처음 5개):\n")
                for bundle in item.bundles[:5]:
                    self.analysis_text.insert(
                        tk.END,
                        f"   {bundle.product_name}/{bundle.material_name} "
                        f"{bundle.quantity}EA: "
                        f"{bundle.start_time:.1f}분 → {bundle.completion_time:.1f}분 "
                        f"({bundle.completion_time - bundle.start_time:.1f}분)\n",
                    )

        self.analysis_text.insert(tk.END, "\n\n병목 분석 및 개선 제안\n")
        self.analysis_text.insert(tk.END, "=" * 70 + "\n")
        self.analysis_text.insert(tk.END, f"\n병목 공정: {bottleneck_name}\n")
        self.analysis_text.insert(tk.END, f"   • {bottleneck_reason}\n")
        self.analysis_text.insert(tk.END, f"   • {bottleneck_impact}\n\n")
        self.analysis_text.insert(tk.END, "개선 방안:\n")
        self.analysis_text.insert(tk.END, "1. 병목 공정의 처리 시간 단축\n")
        self.analysis_text.insert(tk.END, "   - 공정 자동화 검토\n")
        self.analysis_text.insert(tk.END, "   - 작업 방법 개선\n\n")
        self.analysis_text.insert(tk.END, "2. 병목 공정의 동시 가공 수량 증대\n")
        self.analysis_text.insert(tk.END, "   - 설비 대수 증설\n")
        self.analysis_text.insert(tk.END, "   - 병렬 처리 라인 구축\n")

    def _write_block_operation_details(
        self,
        item: BlockResult,
        block: ProcessBlock | None,
    ) -> None:
        if block and block.type == "INPUT":
            self.analysis_text.insert(
                tk.END,
                f"   • 제품명: {block.product_name}\n",
            )
            self.analysis_text.insert(tk.END, f"   • 원자재명: {block.material_name}\n")
            self.analysis_text.insert(tk.END, f"   • 투입 원자재 수: {block.input_quantity} EA\n")
            self.analysis_text.insert(tk.END, f"   • 투입 시간: {block.input_time:g}분\n")
            return
        if block and block.type == "HOIST":
            self.analysis_text.insert(tk.END, f"   • 1회 운반 수량: {block.transport_capacity} EA\n")
            self.analysis_text.insert(tk.END, f"   • 1회 이동 시간: {block.transport_time:g}분\n")
            self.analysis_text.insert(tk.END, f"   • 이론 운반율: {item.throughput:.3f} EA/분\n")
            return

        if block:
            self.analysis_text.insert(
                tk.END,
                f"   • 처리 시간: {block.process_time_per_ea:g}분/EA\n",
            )
            self.analysis_text.insert(
                tk.END,
                f"   • 동시 가공 수량: {block.concurrent_capacity} EA\n",
            )
        self.analysis_text.insert(tk.END, f"   • 이론 처리율: {item.throughput:.3f} EA/분\n")

    def _block_icon(self, block_id: int) -> str:
        block = self.controller.find_block(block_id)
        if not block:
            return ""
        return BLOCK_TYPES[block.type].icon

    def _block_name(self, block_id: int) -> str:
        return self.controller.block_display_name(self.controller.find_block(block_id))

    def _timeline_metric_text(
        self,
        item: BlockResult,
        block: ProcessBlock | None,
    ) -> str:
        if block and block.type == "INPUT":
            return (
                f"투입 {item.total_processed} EA | 묶음 {item.processed_bundle_count}개 | "
                f"투입 시간 {block.input_time:g}분"
            )
        if block and block.type == "HOIST":
            return (
                f"운반 {item.total_processed} EA | 묶음 {item.processed_bundle_count}개 | "
                f"이동 {item.transport_trips}회"
            )
        return (
            f"처리 {item.total_processed} EA | 묶음 {item.processed_bundle_count}개 | "
            f"이론 처리율 {item.throughput:.3f} EA/분"
        )

    def _route_text(self, block_id: int) -> str:
        outgoing = [
            connection
            for connection in self.controller.scenario.connections
            if connection.from_block == block_id
        ]
        if not outgoing:
            return "다음: 종료 공정"

        names = [
            self.controller.block_display_name(
                self.controller.find_block(connection.to_block)
            )
            for connection in outgoing
        ]
        return f"다음: {', '.join(names)}"

    def _bottleneck_name(self, result: SimulationResult) -> str:
        if result.bottleneck_id is None:
            return "없음"
        return self.controller.block_display_name(self.controller.find_block(result.bottleneck_id))
