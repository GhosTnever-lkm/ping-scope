"""PingScope: a small, local Windows network-quality monitor."""

from __future__ import annotations

import csv
import ipaddress
import math
import queue
import re
import socket
import statistics
import subprocess
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from tkinter import filedialog, messagebox, ttk


APP_VERSION = "0.2.4"
MAX_SAMPLES = 10_000
TIME_RE = re.compile(r"(?:time|время)\s*([=<])\s*(\d+(?:[.,]\d+)?)\s*(?:ms|мс)?", re.I)
DOMAIN_RE = re.compile(r"(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)(?:\.(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?))*\.?$")


@dataclass(frozen=True)
class Sample:
    index: int
    timestamp: datetime
    latency_ms: float | None


def validate_target(value: str) -> str:
    """Validate one hostname/IP before passing it as a ping argument."""
    target = value.strip()
    if not target or len(target) > 253 or target.startswith("-") or any(c.isspace() for c in target):
        raise ValueError("Введите IP-адрес или имя узла (например, 1.1.1.1).")
    try:
        ipaddress.ip_address(target)
        return target
    except ValueError:
        pass
    try:
        ascii_name = target.rstrip(".").encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Не удалось распознать имя узла.") from exc
    if not DOMAIN_RE.fullmatch(ascii_name):
        raise ValueError("Имя узла содержит недопустимые символы.")
    return ascii_name


def parse_ping_latency(output: str) -> float | None:
    """Return a numeric response time; None means no recognized reply."""
    match = TIME_RE.search(output)
    if not match:
        return None
    value = float(match.group(2).replace(",", "."))
    return min(0.5, value) if match.group(1) == "<" else value


def ping_once(target: str, timeout_ms: int) -> float | None:
    args = ["ping", "-n", "1", "-w", str(timeout_ms)]
    try:
        ip = ipaddress.ip_address(target)
        args.insert(1, "-6" if ip.version == 6 else "-4")
    except ValueError:
        pass
    args.append(target)
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout_ms / 1000 + 2, check=False,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return None
    for encoding in ("cp866", "cp1251", "utf-8"):
        try:
            output = result.stdout.decode(encoding)
            break
        except UnicodeDecodeError:
            output = result.stdout.decode(encoding, errors="replace")
    return parse_ping_latency(output)


def summarize(samples: list[Sample]) -> dict[str, float | int | None]:
    replies = [s.latency_ms for s in samples if s.latency_ms is not None]
    sent = len(samples)
    loss = (sent - len(replies)) / sent * 100 if sent else 0.0
    deltas = [abs(b - a) for a, b in zip(replies, replies[1:])]
    return {
        "sent": sent,
        "received": len(replies),
        "loss_pct": loss,
        "min_ms": min(replies) if replies else None,
        "avg_ms": statistics.fmean(replies) if replies else None,
        "median_ms": statistics.median(replies) if replies else None,
        "max_ms": max(replies) if replies else None,
        "jitter_ms": statistics.fmean(deltas) if deltas else None,
    }


class PingScope(tk.Tk):
    BG = "#0c111b"
    PANEL = "#141c2b"
    PANEL_2 = "#1b2638"
    TEXT = "#e8edf6"
    MUTED = "#96a5bb"
    BLUE = "#63a8ff"
    GREEN = "#47d7a0"
    RED = "#ff727f"
    GRID = "#29364b"

    def __init__(self) -> None:
        super().__init__()
        self.title("PingScope — диагностика соединения")
        self.geometry("1050x720")
        self.minsize(820, 600)
        self.configure(bg=self.BG)
        self.samples: list[Sample] = []
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.running = False
        self.session_target = ""
        self._style()
        self._layout()
        self.after(100, self._drain_events)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=self.PANEL, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.PANEL, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI Semibold", 23))
        style.configure("Metric.TLabel", background=self.PANEL, foreground=self.TEXT, font=("Segoe UI Semibold", 19))
        style.configure("TEntry", fieldbackground=self.PANEL_2, foreground=self.TEXT, insertcolor=self.TEXT, padding=8)
        style.configure("TCombobox", fieldbackground=self.PANEL_2, background=self.PANEL_2, foreground=self.TEXT, padding=6)
        style.configure("Accent.TButton", background=self.BLUE, foreground="#07111f", padding=(14, 9), font=("Segoe UI Semibold", 10), borderwidth=0)
        style.map("Accent.TButton", background=[("disabled", "#34445b"), ("active", "#8bc0ff")])
        style.configure("Quiet.TButton", background=self.PANEL_2, foreground=self.TEXT, padding=(12, 8), borderwidth=0)
        style.map("Quiet.TButton", background=[("active", "#2a3950")])

    def _layout(self) -> None:
        outer = ttk.Frame(self, padding=(26, 22, 26, 20))
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(0, 18))
        ttk.Label(top, text="PingScope", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="LOCAL NETWORK LAB  ·  v" + APP_VERSION, foreground=self.MUTED).pack(side="left", padx=16, pady=(9, 0))
        ttk.Label(top, text="Ваши замеры остаются на этом компьютере", foreground=self.MUTED).pack(side="right", pady=(9, 0))

        controls = ttk.Frame(outer, style="Panel.TFrame", padding=16)
        controls.pack(fill="x", pady=(0, 14))
        ttk.Label(controls, text="АДРЕС УЗЛА", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.target_var = tk.StringVar(value="1.1.1.1")
        self.target_entry = ttk.Entry(controls, textvariable=self.target_var, width=28)
        self.target_entry.grid(row=1, column=0, sticky="ew", padx=(0, 14), pady=(5, 0))
        ttk.Label(controls, text="ИНТЕРВАЛ", style="Muted.TLabel").grid(row=0, column=1, sticky="w")
        self.interval_var = tk.StringVar(value="1.0")
        ttk.Combobox(controls, textvariable=self.interval_var, values=("0.5", "1.0", "2.0", "5.0"), state="readonly", width=8).grid(row=1, column=1, sticky="w", padx=(0, 14), pady=(5, 0))
        ttk.Label(controls, text="ТАЙМАУТ", style="Muted.TLabel").grid(row=0, column=2, sticky="w")
        self.timeout_var = tk.StringVar(value="1200")
        ttk.Combobox(controls, textvariable=self.timeout_var, values=("500", "1200", "2500", "5000"), state="readonly", width=9).grid(row=1, column=2, sticky="w", padx=(0, 14), pady=(5, 0))
        self.start_button = ttk.Button(controls, text="▶  Начать замер", style="Accent.TButton", command=self.start)
        self.start_button.grid(row=1, column=3, sticky="ew", pady=(5, 0), padx=(0, 8))
        self.stop_button = ttk.Button(controls, text="■  Стоп", style="Quiet.TButton", command=self.stop, state="disabled")
        self.stop_button.grid(row=1, column=4, sticky="ew", pady=(5, 0))
        controls.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Готов к замеру · выберите узел или введите адрес вручную")
        ttk.Label(outer, textvariable=self.status_var, foreground=self.MUTED).pack(fill="x", pady=(0, 12))

        metric_row = ttk.Frame(outer)
        metric_row.pack(fill="x", pady=(0, 14))
        self.metric_vars: dict[str, tk.StringVar] = {}
        metrics = [("СРЕДНЯЯ ЗАДЕРЖКА", "avg_ms", "ms"), ("ДЖИТТЕР", "jitter_ms", "ms"), ("ПОТЕРИ", "loss_pct", "%"), ("ПАКЕТЫ", "sent", "")]
        for i, (label, key, suffix) in enumerate(metrics):
            card = ttk.Frame(metric_row, style="Panel.TFrame", padding=(15, 12))
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            ttk.Label(card, text=label, style="Muted.TLabel").pack(anchor="w")
            value = tk.StringVar(value="—")
            self.metric_vars[key] = value
            val = ttk.Label(card, textvariable=value, style="Metric.TLabel")
            val.pack(anchor="w", pady=(5, 0))
            if key == "loss_pct":
                self.loss_value_label = val
            metric_row.columnconfigure(i, weight=1)

        graph_card = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        graph_card.pack(fill="both", expand=True)
        graph_header = ttk.Frame(graph_card, style="Panel.TFrame")
        graph_header.pack(fill="x", pady=(0, 8))
        ttk.Label(graph_header, text="ЗАДЕРЖКА ВО ВРЕМЕНИ", style="Muted.TLabel").pack(side="left")
        ttk.Label(graph_header, text="● ответ  ·  × потеря  ·  шкала подстраивается", style="Muted.TLabel").pack(side="right")
        self.canvas = tk.Canvas(graph_card, bg=self.PANEL, highlightthickness=0, height=250)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._draw_graph())

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(13, 0))
        ttk.Label(footer, text="Статистика: min / avg / median / max · джиттер как средняя разница между ответами", foreground=self.MUTED).pack(side="left")
        ttk.Button(footer, text="Сбросить", style="Quiet.TButton", command=self.reset).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Экспорт CSV…", style="Quiet.TButton", command=self.export_csv).pack(side="right")

    def start(self) -> None:
        if self.running:
            return
        try:
            target = validate_target(self.target_var.get())
            interval = float(self.interval_var.get())
            timeout = int(self.timeout_var.get())
            if interval < 0.5 or timeout < 100 or timeout > 10_000:
                raise ValueError("Интервал должен быть не меньше 0,5 с, таймаут — от 100 до 10000 мс.")
        except ValueError as exc:
            messagebox.showerror("Проверьте параметры", str(exc), parent=self)
            return
        if self.samples and not messagebox.askyesno(
            "Начать новый сеанс?",
            f"Есть {len(self.samples)} замеров предыдущего сеанса. Новый сеанс очистит их. "
            "Перед продолжением нажмите «Экспорт CSV…», если хотите сохранить результаты.",
            parent=self,
        ):
            return
        if self.samples:
            self.reset()
        self.session_target = target
        self.stop_event.clear()
        self.running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.target_entry.configure(state="disabled")
        self.status_var.set(f"Идёт замер {target} · остановите в любой момент")
        self.worker = threading.Thread(target=self._sample_loop, args=(target, interval, timeout), daemon=True)
        self.worker.start()

    def _sample_loop(self, target: str, interval: float, timeout: int) -> None:
        sample_index = 0
        while not self.stop_event.is_set() and sample_index < MAX_SAMPLES:
            started = time.monotonic()
            latency = ping_once(target, timeout)
            sample_index += 1
            self.events.put(("sample", Sample(sample_index, datetime.now().astimezone(), latency)))
            self.stop_event.wait(max(0.0, interval - (time.monotonic() - started)))
        self.events.put(("done", "Лимит 10 000 замеров достигнут" if sample_index >= MAX_SAMPLES else "Замер остановлен"))

    def stop(self) -> None:
        if self.running:
            self.stop_event.set()

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "sample":
                    self.samples.append(payload)  # type: ignore[arg-type]
                    self._update_metrics()
                    self._draw_graph()
                else:
                    self.running = False
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.target_entry.configure(state="normal")
                    self.status_var.set(f"{payload} · {len(self.samples)} пакетов · {self.session_target}")
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _update_metrics(self) -> None:
        stats = summarize(self.samples)
        for key in ("avg_ms", "jitter_ms"):
            value = stats[key]
            self.metric_vars[key].set("—" if value is None else f"{value:.1f}")
        self.metric_vars["loss_pct"].set(f"{stats['loss_pct']:.0f}")
        self.metric_vars["sent"].set(f"{stats['received']}/{stats['sent']}")
        self.loss_value_label.configure(foreground=self.RED if float(stats["loss_pct"]) > 5 else self.GREEN)

    def _draw_graph(self) -> None:
        c = self.canvas
        c.delete("all")
        width, height = c.winfo_width(), c.winfo_height()
        if width < 80 or height < 80:
            return
        left, right, top, bottom = 52, width - 18, 18, height - 30
        visible = self.samples[-200:]
        values = [s.latency_ms for s in visible if s.latency_ms is not None]
        ymax = max(50.0, math.ceil(max(values, default=40) / 10) * 10)
        for tick in range(5):
            yv = ymax * tick / 4
            y = bottom - (bottom - top) * tick / 4
            c.create_line(left, y, right, y, fill=self.GRID)
            c.create_text(left - 8, y, text=f"{yv:.0f}", fill=self.MUTED, anchor="e", font=("Segoe UI", 8))
        c.create_text(8, top, text="ms", fill=self.MUTED, anchor="w", font=("Segoe UI", 8))
        if not visible:
            c.create_text((left + right) / 2, (top + bottom) / 2, text="Запустите замер — здесь появится график", fill=self.MUTED, font=("Segoe UI", 11))
            return
        span_x = max(1, len(visible) - 1)
        coords: list[float] = []
        for i, sample in enumerate(visible):
            x = left + (right - left) * i / span_x
            if sample.latency_ms is None:
                c.create_text(x, bottom - 5, text="×", fill=self.RED, font=("Segoe UI Semibold", 12))
                if len(coords) >= 4:
                    c.create_line(*coords, fill=self.BLUE, width=2, smooth=True)
                coords = []
                continue
            y = bottom - min(sample.latency_ms, ymax) / ymax * (bottom - top)
            coords.extend((x, y))
            c.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5, fill=self.GREEN, outline="")
        if len(coords) >= 4:
            c.create_line(*coords, fill=self.BLUE, width=2, smooth=True)
        if len(visible) > 1:
            c.create_text(left, height - 7, text=f"#{visible[0].index}", fill=self.MUTED, anchor="w", font=("Segoe UI", 8))
            c.create_text(right, height - 7, text=f"#{visible[-1].index}", fill=self.MUTED, anchor="e", font=("Segoe UI", 8))

    def reset(self) -> None:
        if self.running:
            messagebox.showinfo("Сначала остановите замер", "Остановите текущий замер, затем сбросьте результаты.", parent=self)
            return
        self.samples.clear()
        self.session_target = ""
        for value in self.metric_vars.values():
            value.set("—")
        self.status_var.set("Готов к замеру · выберите узел или введите адрес вручную")
        self.loss_value_label.configure(foreground=self.TEXT)
        self._draw_graph()

    def export_csv(self) -> None:
        if not self.samples:
            messagebox.showinfo("Нет результатов", "Сначала выполните хотя бы один замер.", parent=self)
            return
        suggested = f"pingscope-{datetime.now():%Y%m%d-%H%M%S}.csv"
        path = filedialog.asksaveasfilename(parent=self, title="Сохранить отчёт", initialfile=suggested,
                                            defaultextension=".csv", filetypes=(("CSV", "*.csv"),))
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(("target", self.session_target))
                writer.writerow(("sent", len(self.samples), "received", sum(s.latency_ms is not None for s in self.samples)))
                stats = summarize(self.samples)
                writer.writerow(("packet_loss_pct", f"{stats['loss_pct']:.2f}", "avg_ms", stats["avg_ms"], "jitter_ms", stats["jitter_ms"]))
                writer.writerow(("sequence", "timestamp_local", "latency_ms", "result"))
                for sample in self.samples:
                    writer.writerow((sample.index, sample.timestamp.isoformat(timespec="seconds"),
                                     "" if sample.latency_ms is None else f"{sample.latency_ms:.2f}",
                                     "timeout" if sample.latency_ms is None else "reply"))
        except OSError as exc:
            messagebox.showerror("Не удалось сохранить", str(exc), parent=self)
            return
        self.status_var.set(f"CSV сохранён · {path}")


if __name__ == "__main__":
    PingScope().mainloop()
