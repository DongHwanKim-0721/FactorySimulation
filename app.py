from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from engine.models import ProcessBlock, ProcessConnection, Scenario
from engine.scenario_io import load as load_scenario_file
from engine.scenario_io import save as save_scenario_file
from engine.simulation import BlockResult, SimulationResult, simulate


@dataclass(frozen=True)
class BlockType:
    label: str
    color: str
    icon: str
    default_time: float


BLOCK_TYPES: dict[str, BlockType] = {
    "INPUT": BlockType("원자재 투입", "#3b82f6", "📥", 30),
    "STORAGE": BlockType("적재", "#10b981", "📦", 15),
    "CUTTING": BlockType("절단기", "#f59e0b", "✂️", 45),
    "STRAIGHTNESS": BlockType("자동진직도 측정기", "#8b5cf6", "📏", 20),
    "HEAT": BlockType("열처리기", "#ef4444", "🔥", 120),
    "PRESS": BlockType("프레스 교정기", "#ec4899", "⚙️", 60),
    "FREE": BlockType("Free Block", "#6b7280", "📋", 30),
}


class App:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("공정 시뮬레이션 프로그램 v1.2")
        self.root.geometry("1600x900")
        self.root.minsize(1200, 700)

        style = ttk.Style()
        style.theme_use("clam")

        self.scenario = Scenario()
        self.last_result: SimulationResult | None = None
        self.units_per_source_var = tk.IntVar(value=10)
        self.connection_start_id: int | None = None
        self.status_var = tk.StringVar(value="준비 완료")

        self._create_widgets()
        self.root.bind("<Escape>", self.cancel_connection)

    def _create_widgets(self) -> None:
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(main_frame, relief=tk.RAISED, padding=5)
        toolbar.pack(fill=tk.X)
        ttk.Label(
            toolbar,
            text="공정 시뮬레이션 프로그램 v1.2",
            font=("Arial", 16, "bold"),
        ).pack(side=tk.LEFT, padx=10)

        button_frame = ttk.Frame(toolbar)
        button_frame.pack(side=tk.RIGHT, padx=10)
        ttk.Label(button_frame, text="시작 공정별 투입 수량(EA)").pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Entry(button_frame, textvariable=self.units_per_source_var, width=6).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(button_frame, text="시뮬레이션 실행", command=self.run_simulation).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(button_frame, text="저장", command=self.save_scenario).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(button_frame, text="불러오기", command=self.load_scenario).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(button_frame, text="초기화", command=self.clear_all).pack(
            side=tk.LEFT, padx=2
        )

        content_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        content_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(content_paned, width=240)
        center_frame = ttk.Frame(content_paned)
        right_frame = ttk.Frame(content_paned, width=420)
        content_paned.add(left_frame, weight=0)
        content_paned.add(center_frame, weight=3)
        content_paned.add(right_frame, weight=1)

        self.palette_view = PaletteView(left_frame, self)
        self.canvas_view = CanvasView(center_frame, self)
        self.result_view = ResultView(right_frame, self)

        status_bar = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

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
            process_time=block_type_info.default_time,
            custom_name=custom_name,
        )
        self.canvas_view.redraw()
        self.status_var.set(f"{self.block_display_name(block)} 블록이 추가되었습니다.")

    def prompt_free_block_name(self) -> str:
        dialog = tk.Toplevel(self.root)
        dialog.title("Free Block 이름 입력")
        dialog.geometry("400x180")
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
        dialog.geometry("400x270")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text=f"{block_type_info.icon} {self.block_display_name(block)}",
            font=("Arial", 14, "bold"),
        ).pack(fill=tk.X, padx=20, pady=12)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        row = 0
        name_var = tk.StringVar(value=block.custom_name)
        if block.type == "FREE":
            ttk.Label(form_frame, text="블록 이름:").grid(
                row=row, column=0, sticky=tk.W, pady=5
            )
            ttk.Entry(form_frame, textvariable=name_var, width=22).grid(
                row=row, column=1, sticky=tk.W, pady=5
            )
            row += 1

        time_var = tk.DoubleVar(value=block.process_time)
        capacity_var = tk.IntVar(value=block.capacity)

        ttk.Label(form_frame, text="처리 시간(분/EA):").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        ttk.Entry(form_frame, textvariable=time_var, width=22).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )
        row += 1

        ttk.Label(form_frame, text="동시 처리 수량(EA):").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        ttk.Entry(form_frame, textvariable=capacity_var, width=22).grid(
            row=row, column=1, sticky=tk.W, pady=5
        )

        def save_params() -> None:
            try:
                process_time = float(time_var.get())
                capacity = int(capacity_var.get())
            except tk.TclError:
                messagebox.showerror(
                    "입력 오류",
                    "처리 시간과 동시 처리 수량은 숫자로 입력해주세요.",
                )
                return

            if process_time <= 0 or capacity <= 0:
                messagebox.showerror(
                    "입력 오류",
                    "처리 시간은 0보다 커야 하고 동시 처리 수량은 1 이상이어야 합니다.",
                )
                return

            if block.type == "FREE":
                block.custom_name = name_var.get().strip()
            block.process_time = process_time
            block.capacity = capacity
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
        self.canvas_view.redraw()

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
        self.canvas_view.redraw()
        self.status_var.set("연결이 삭제되었습니다.")

    def run_simulation(self) -> None:
        if not self.scenario.blocks:
            messagebox.showwarning("경고", "공정 블록을 추가해주세요.")
            return

        try:
            units_per_source = int(self.units_per_source_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("입력 오류", "시작 공정별 투입 수량(EA)은 정수로 입력해주세요.")
            return

        if units_per_source < 0:
            messagebox.showerror("입력 오류", "시작 공정별 투입 수량(EA)은 0 이상이어야 합니다.")
            return

        try:
            result = simulate(
                self.scenario.blocks,
                self.scenario.connections,
                units_per_source=units_per_source,
            )
        except ValueError as exc:
            messagebox.showerror("시뮬레이션 오류", str(exc))
            return

        if not result.timeline:
            messagebox.showerror("오류", "시뮬레이션 결과가 없습니다.")
            return

        self.last_result = result
        self.result_view.display(result)
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
        self.canvas_view.redraw()
        self.result_view.clear()
        messagebox.showinfo("불러오기 완료", "시나리오가 불러와졌습니다.")
        self.status_var.set(f"시나리오 불러옴: {filename}")

    def clear_all(self) -> None:
        if not messagebox.askyesno("초기화 확인", "모든 블록과 연결을 삭제하시겠습니까?"):
            return
        self.scenario = Scenario()
        self.last_result = None
        self.connection_start_id = None
        self.canvas_view.redraw()
        self.result_view.clear()
        self.status_var.set("초기화 완료")

    def block_display_name(self, block: ProcessBlock | None) -> str:
        if block is None:
            return "Unknown"
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
        return (
            f"이론 처리율 {result.bottleneck_throughput:.3f} EA/분 "
            f"(동시 처리 수량 {block.capacity} EA / 처리 시간 {block.process_time:g}분/EA)"
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
        self.frame = ttk.LabelFrame(parent, text="공정 블록 팔레트", padding=10)
        self.frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._create_widgets()

    def _create_widgets(self) -> None:
        canvas = tk.Canvas(self.frame, width=250, bg="#dcdad5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for key, block_type in BLOCK_TYPES.items():
            button = tk.Button(
                scrollable_frame,
                text=f"{block_type.icon} {block_type.label}\n({block_type.default_time:g}분/EA)",
                bg=block_type.color,
                fg="white",
                font=("Arial", 10, "bold"),
                relief=tk.RAISED,
                bd=2,
                cursor="hand2",
                command=lambda block_key=key: self.controller.add_block(block_key),
            )
            button.pack(fill=tk.X, pady=5, ipady=10)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


class CanvasView:
    def __init__(self, parent: tk.Widget, controller: App) -> None:
        self.controller = controller
        self.drag_block_id: int | None = None
        self.drag_x = 0.0
        self.drag_y = 0.0

        self.frame = ttk.LabelFrame(parent, text="공정 다이어그램", padding=5)
        self.frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(self.frame, bg="#f0f0f0", cursor="cross")
        h_scroll = ttk.Scrollbar(self.frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scroll = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
            scrollregion=(0, 0, 2000, 2000),
        )

        self.canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        self.frame.grid_rowconfigure(0, weight=1)
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
        for connection in self.controller.scenario.connections:
            self.draw_connection(connection)
        for block in self.controller.scenario.blocks:
            self.draw_block(block)

    def draw_block(self, block: ProcessBlock) -> None:
        block_type = BLOCK_TYPES[block.type]
        display_name = self.controller.block_display_name(block)

        self.canvas.create_rectangle(
            block.x,
            block.y,
            block.x + block.width,
            block.y + block.height,
            fill=block_type.color,
            outline="white",
            width=3,
            tags=f"block_{block.id}",
        )
        self.canvas.create_text(
            block.x + 20,
            block.y + 20,
            text=block_type.icon,
            font=("Arial", 20),
            tags=f"block_{block.id}",
        )
        self.canvas.create_text(
            block.x + 75,
            block.y + 20,
            text=display_name,
            font=("Arial", 9, "bold"),
            fill="white",
            tags=f"block_{block.id}",
        )
        self.canvas.create_text(
            block.x + 75,
            block.y + 45,
            text=f"시간: {block.process_time:g}분/EA",
            font=("Arial", 8),
            fill="white",
            tags=f"block_{block.id}",
        )
        self.canvas.create_text(
            block.x + 75,
            block.y + 60,
            text=f"동시: {block.capacity} EA",
            font=("Arial", 8),
            fill="white",
            tags=f"block_{block.id}",
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
            fill="#64748b",
            width=5,
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

    def show_connection_start(self, block_id: int) -> None:
        block = self.controller.find_block(block_id)
        if not block:
            return
        self.canvas.config(cursor="tcross", bg="#fff5f5")
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
        self.canvas.config(cursor="cross", bg="#f0f0f0")
        self.canvas.delete("connection_highlight")

    def on_click(self, event: tk.Event) -> None:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        connection_id = self._connection_delete_at(x, y)
        if connection_id is not None:
            self.controller.delete_connection(connection_id)
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


class ResultView:
    def __init__(self, parent: tk.Widget, controller: App) -> None:
        self.controller = controller
        self.frame = ttk.LabelFrame(parent, text="시뮬레이션 결과", padding=5)
        self.frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        summary_frame = ttk.Frame(notebook)
        timeline_frame = ttk.Frame(notebook)
        analysis_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="요약")
        notebook.add(timeline_frame, text="타임라인")
        notebook.add(analysis_frame, text="분석")

        self.summary_text = tk.Text(
            summary_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            bg="#f8f9fa",
            width=40,
            height=12,
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True)

        self.timeline_canvas = tk.Canvas(timeline_frame, bg="#ffffff", width=380, height=300)
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
            bg="#f8f9fa",
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

    def display(self, result: SimulationResult) -> None:
        self.clear()
        bottleneck_name = self._bottleneck_name(result)
        bottleneck_reason = self.controller.bottleneck_reason(result)
        bottleneck_impact = self.controller.bottleneck_impact(result)

        self.summary_text.insert(tk.END, "=" * 40 + "\n")
        self.summary_text.insert(tk.END, "   EA 단위 시뮬레이션 결과\n")
        self.summary_text.insert(tk.END, "=" * 40 + "\n\n")
        self.summary_text.insert(tk.END, f"총 시뮬레이션 시간: {result.total_time:.1f}분\n")
        self.summary_text.insert(tk.END, f"시작 공정 수: {result.source_count}개\n")
        self.summary_text.insert(
            tk.END,
            f"시작 공정별 투입 수량: {result.units_per_source} EA\n",
        )
        self.summary_text.insert(
            tk.END,
            f"전체 투입 수량: {result.total_generated_units} EA\n\n",
        )
        self.summary_text.insert(tk.END, f"병목 공정: {bottleneck_name}\n")
        self.summary_text.insert(tk.END, f"   이유: {bottleneck_reason}\n")
        self.summary_text.insert(tk.END, f"   영향: {bottleneck_impact}\n\n")
        self.summary_text.insert(tk.END, f"공정 수: {len(result.timeline)}개\n")

        avg_cycle = (
            result.total_time / result.total_generated_units
            if result.total_generated_units > 0
            else 0
        )
        self.summary_text.insert(tk.END, f"평균 소요 시간: {avg_cycle:.1f}분/EA\n")

        self._draw_timeline(result)
        self._write_analysis(result, bottleneck_name, bottleneck_reason, bottleneck_impact)

    def _draw_timeline(self, result: SimulationResult) -> None:
        y_offset = 30
        self.timeline_canvas.create_text(
            10,
            y_offset,
            text="공정 흐름 및 성능",
            anchor=tk.W,
            font=("Arial", 11, "bold"),
        )
        y_offset += 30

        max_throughput = max((item.throughput for item in result.timeline), default=0)
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
                text=(
                    f"시간: {item.process_time:g}분/EA | 동시: {item.capacity} EA | "
                    f"이론 처리율: {item.throughput:.3f} EA/분"
                ),
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

            bar_x = 210
            bar_width = 120
            bar_height = 20
            bar_length = (item.throughput / max_throughput) * bar_width if max_throughput else 0
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

            if idx < len(result.timeline) - 1:
                self.timeline_canvas.create_text(
                    10,
                    y_offset + 50,
                    text="↓",
                    anchor=tk.W,
                    font=("Arial", 12),
                    fill="#64748b",
                )
                y_offset += 70
            else:
                y_offset += 50

        self.timeline_canvas.configure(scrollregion=self.timeline_canvas.bbox("all"))

    def _write_analysis(
        self,
        result: SimulationResult,
        bottleneck_name: str,
        bottleneck_reason: str,
        bottleneck_impact: str,
    ) -> None:
        self.analysis_text.insert(tk.END, "=" * 70 + "\n")
        self.analysis_text.insert(tk.END, "              EA 단위 시뮬레이션 상세 분석\n")
        self.analysis_text.insert(tk.END, "=" * 70 + "\n\n")

        self.analysis_text.insert(tk.END, "공정 흐름\n")
        self.analysis_text.insert(tk.END, "-" * 70 + "\n")
        flow_diagram = " → ".join(
            [
                f"{self._block_icon(item.block_id)}{self.controller.block_result_display_name(item)}"
                for item in result.timeline
            ]
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
            self.analysis_text.insert(tk.END, "   기본 정보:\n")
            self.analysis_text.insert(tk.END, f"   • 처리 시간: {item.process_time:g}분/EA\n")
            self.analysis_text.insert(tk.END, f"   • 동시 처리 수량: {item.capacity} EA\n")
            self.analysis_text.insert(tk.END, f"   • 이론 처리율: {item.throughput:.3f} EA/분\n")
            self.analysis_text.insert(tk.END, f"   • 실제 처리 수량: {item.total_processed} EA\n")
            self.analysis_text.insert(tk.END, "\n   성능 지표:\n")
            self.analysis_text.insert(tk.END, f"   • 단위 처리 시간: {item.process_time:.1f}분/EA\n")
            self.analysis_text.insert(tk.END, f"   • 평균 대기 시간: {item.avg_waiting:.1f}분\n")

            if item.block_id == result.bottleneck_id:
                self.analysis_text.insert(tk.END, "\n   병목 공정\n")
                self.analysis_text.insert(tk.END, f"   → {bottleneck_reason}\n")
                self.analysis_text.insert(tk.END, "   → 전체 공정의 처리 속도를 제한하는 구간입니다.\n")

            if item.start_times:
                self.analysis_text.insert(tk.END, "\n   EA별 타임라인 (처음 3개):\n")
                for batch_idx in range(min(3, len(item.start_times))):
                    start = item.start_times[batch_idx]
                    end = item.completion_times[batch_idx]
                    self.analysis_text.insert(
                        tk.END,
                        f"   EA {batch_idx + 1}: {start:.1f}분 → {end:.1f}분 "
                        f"({end - start:.1f}분)\n",
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
        self.analysis_text.insert(tk.END, "2. 병목 공정의 동시 처리 수량 증대\n")
        self.analysis_text.insert(tk.END, "   - 설비 대수 증설\n")
        self.analysis_text.insert(tk.END, "   - 병렬 처리 라인 구축\n")

    def _block_icon(self, block_id: int) -> str:
        block = self.controller.find_block(block_id)
        if not block:
            return ""
        return BLOCK_TYPES[block.type].icon

    def _bottleneck_name(self, result: SimulationResult) -> str:
        if result.bottleneck_id is None:
            return "없음"
        return self.controller.block_display_name(self.controller.find_block(result.bottleneck_id))
