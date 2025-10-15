from __future__ import annotations
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional, Tuple

from proxy.models import Proxy
from proxy.parse import parse_lines_to_candidates
from proxy.pool import ProxyPool
from proxy.sources import gather_proxies_from_sources
from proxy.validate import ValidationResult, validate_proxy
from tools.logging_setup import get_logger

log = get_logger(__name__)

ApplyCallback = Callable[[Proxy, Optional[ValidationResult]], None]
Key = Tuple[str, str, int, str]


class ProxyLabFrame(ttk.LabelFrame):
    def __init__(
        self,
        master,
        *,
        apply_callback: Optional[ApplyCallback] = None,
        scheme_getter: Optional[Callable[[], str]] = None,
        country_getter: Optional[Callable[[], str]] = None,
        **kwargs,
    ):
        super().__init__(master, text="Proxy Lab", **kwargs)
        self.pool = ProxyPool()
        self.apply_callback = apply_callback
        self.scheme_getter = scheme_getter
        self.country_getter = country_getter

        self.queue: queue.Queue = queue.Queue()
        self._parsed: List[Proxy] = []
        self._results: List[Tuple[Proxy, ValidationResult]] = []
        self._result_map: Dict[Key, Tuple[Proxy, ValidationResult]] = {}
        self._tree_map: Dict[Key, str] = {}
        self._ok_list: List[Tuple[Proxy, ValidationResult]] = []
        self._ok_index: int = 0
        self._pending_action: Optional[str] = None
        self._validation_total: int = 0

        self._build()
        self.sync_with_parent(
            scheme_getter() if scheme_getter else None,
            country_getter() if country_getter else None,
        )

    # ------------------------------------------------------------------
    # UI construction and helpers
    def _build(self) -> None:
        self.txt = tk.Text(self, height=6)
        self.txt.grid(row=0, column=0, columnspan=5, sticky="nsew", padx=6, pady=6)
        self._attach_context_menu(self.txt)

        ttk.Label(self, text="Тип:").grid(row=1, column=0, sticky="w", padx=6)
        self.cmb_type = ttk.Combobox(self, values=["http", "socks4", "socks5"], width=8)
        self.cmb_type.set("http")
        self.cmb_type.grid(row=1, column=1, sticky="w")
        ttk.Label(self, text="Страна (ISO):").grid(row=1, column=2, sticky="e")
        self.ent_cc = ttk.Entry(self, width=8)
        self.ent_cc.grid(row=1, column=3, sticky="w")
        self._attach_context_menu(self.ent_cc)
        self.btn_parse = ttk.Button(self, text="Парсить", command=self._on_parse)
        self.btn_parse.grid(row=1, column=4, sticky="e", padx=6)

        columns = ("host", "scheme", "port", "user", "country", "ping", "ok")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=8)
        widths = (180, 70, 80, 120, 80, 70, 50)
        for column, width in zip(columns, widths):
            self.tree.heading(column, text=column.upper())
            self.tree.column(column, width=width, anchor="center")
        self.tree.grid(row=2, column=0, columnspan=5, sticky="nsew", padx=6, pady=6)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_apply_button())
        self.tree.bind("<Double-1>", lambda _e: self._apply_selected())

        self.prog = ttk.Progressbar(self, mode="indeterminate")
        self.prog.grid(row=3, column=0, columnspan=5, sticky="ew", padx=6)
        self.prog.grid_remove()

        self.btn_next = ttk.Button(self, text="Следующий", command=self.auto_pick_next, state="disabled")
        self.btn_next.grid(row=4, column=0, sticky="w", padx=6, pady=6)
        self.btn_val = ttk.Button(self, text="Валидировать", command=self._on_validate, state="disabled")
        self.btn_val.grid(row=4, column=3, sticky="e", padx=6, pady=6)
        self.btn_add = ttk.Button(self, text="Добавить в пул", command=self._on_add, state="disabled")
        self.btn_add.grid(row=4, column=4, sticky="e", padx=6, pady=6)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var).grid(row=5, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))
        self.btn_best = ttk.Button(self, text="Автовыбор", command=self.auto_pick_best, state="disabled")
        self.btn_best.grid(row=5, column=3, sticky="e", padx=6, pady=(0, 6))
        self.btn_apply = ttk.Button(self, text="Применить выбранный", command=self._apply_selected, state="disabled")
        self.btn_apply.grid(row=5, column=4, sticky="e", padx=6, pady=(0, 6))

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Context menu helpers (Cut / Copy / Paste / Select All)
    def _attach_context_menu(self, widget: tk.Widget) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Вырезать (Ctrl+X)", command=lambda w=widget: w.event_generate("<<Cut>>"))
        menu.add_command(label="Копировать (Ctrl+C)", command=lambda w=widget: w.event_generate("<<Copy>>"))
        menu.add_command(label="Вставить (Ctrl+V)", command=lambda w=widget: w.event_generate("<<Paste>>"))
        menu.add_separator()
        # Text and Entry both support <<SelectAll>> in Tk
        menu.add_command(label="Выделить всё (Ctrl+A)", command=lambda w=widget: w.event_generate("<<SelectAll>>"))

        def show_menu(event: tk.Event) -> None:
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        # Right-click on Windows/X11; on macOS it is also generated for ctrl-click in many setups
        widget.bind("<Button-3>", show_menu, add="+")

    def sync_with_parent(self, scheme: Optional[str], country: Optional[str]) -> None:
        if scheme:
            self.cmb_type.set(scheme.lower())
        if country is not None:
            self.ent_cc.delete(0, tk.END)
            if country:
                self.ent_cc.insert(0, country.upper())

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _make_key(self, proxy: Proxy) -> Key:
        return (proxy.scheme.lower(), proxy.host, int(proxy.port), proxy.username or "")

    def _select_in_tree(self, proxy: Proxy) -> None:
        key = self._make_key(proxy)
        iid = self._tree_map.get(key)
        if iid:
            self.tree.selection_set(iid)
            self.tree.see(iid)

    # ------------------------------------------------------------------
    # Parsing and fetching
    def _on_parse(self) -> None:
        self._reset_state()
        scheme = (self.scheme_getter() or self.cmb_type.get()).lower() if self.scheme_getter else self.cmb_type.get().lower()
        country = (self.country_getter() or self.ent_cc.get()).strip().upper() if self.country_getter else self.ent_cc.get().strip().upper()
        manual_lines = [ln.strip() for ln in self.txt.get("1.0", "end").splitlines() if ln.strip()]
        default_country = country or None
        self.sync_with_parent(scheme, country)

        if manual_lines:
            self._parsed = parse_lines_to_candidates(manual_lines, default_scheme=scheme, default_country=default_country)
            self._populate_tree(self._parsed)
            self.btn_val.config(state="normal" if self._parsed else "disabled")
            self.btn_add.config(state="disabled")
            if self._pending_action:
                self._begin_validation(auto=True)
            return

        # auto fetch from sources
        self.btn_parse.config(state="disabled")
        self.btn_val.config(state="disabled")
        self.btn_add.config(state="disabled")
        self.btn_best.config(state="disabled")
        self.btn_next.config(state="disabled")
        self.prog.grid()
        self.prog.start(12)
        self._set_status("Загружаю прокси из источников...")

        def worker() -> None:
            proxies = gather_proxies_from_sources(default_country, scheme)
            self.after(0, lambda: self._after_fetch(proxies))

        threading.Thread(target=worker, daemon=True).start()

    def _after_fetch(self, proxies: List[Proxy]) -> None:
        self.prog.stop()
        self.prog.grid_remove()
        self.btn_parse.config(state="normal")
        self._parsed = proxies
        if not proxies:
            self._pending_action = None
            self.btn_val.config(state="disabled")
            self._set_status("Источники не дали прокси. Попробуйте позже или вставьте список вручную.")
            return
        self._populate_tree(proxies)
        self.btn_val.config(state="normal")
        if self._pending_action:
            self._begin_validation(auto=True)

    def _populate_tree(self, proxies: List[Proxy]) -> None:
        self.tree.delete(*self.tree.get_children())
        self._tree_map.clear()
        for proxy in proxies:
            values = (
                proxy.host,
                proxy.scheme,
                proxy.port,
                proxy.username or "",
                proxy.country or "",
                "",
                "",
            )
            iid = self.tree.insert("", "end", values=values)
            self._tree_map[self._make_key(proxy)] = iid
        self._set_status(f"Найдено {len(proxies)} прокси")
        self._update_apply_button()

    def _reset_state(self) -> None:
        self._parsed = []
        self._results = []
        self._result_map.clear()
        self._ok_list = []
        self._ok_index = 0
        self._validation_total = 0
        self._pending_action = None if self._pending_action not in {"first", "next"} else self._pending_action
        self.btn_best.config(state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_add.config(state="disabled")
        self.btn_apply.config(state="disabled")
        self.prog.stop()
        self.prog.grid_remove()
        self._set_status("")

    # ------------------------------------------------------------------
    # Validation
    def _begin_validation(self, *, auto: bool = False) -> None:
        if not self._parsed:
            messagebox.showinfo("Proxy Lab", "Нет данных для проверки. Сначала нажмите «Парсить».")
            return
        self.btn_val.config(state="disabled")
        self.btn_add.config(state="disabled")
        self.btn_best.config(state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_apply.config(state="disabled")
        self.prog.grid()
        self.prog.start(12)
        self._set_status(f"Проверяю {len(self._parsed)} прокси...")
        self._results = []
        self._result_map.clear()
        self._ok_list = []
        self._ok_index = 0
        self._validation_total = len(self._parsed)
        self.queue = queue.Queue()
        threading.Thread(target=self._worker_validate, args=(self._parsed,), daemon=True).start()
        self.after(50, self._poll_results)

    def _worker_validate(self, items: List[Proxy]) -> None:
        for proxy in items:
            result = validate_proxy(proxy)
            self.queue.put((proxy, result))
        self.queue.put(None)

    def _on_validate(self) -> None:
        self._pending_action = None
        self._begin_validation(auto=False)

    def _poll_results(self) -> None:
        try:
            item = self.queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_results)
            return
        if item is None:
            self._on_validation_complete()
            return
        proxy, result = item
        key = self._make_key(proxy)
        self._results.append((proxy, result))
        self._result_map[key] = (proxy, result)
        iid = self._tree_map.get(key)
        if iid:
            self.tree.item(
                iid,
                values=(
                    proxy.host,
                    proxy.scheme,
                    proxy.port,
                    proxy.username or "",
                    proxy.country or "",
                    result.ping_ms or "",
                    "yes" if result.ok else "no",
                ),
            )
        ok_count = sum(1 for _p, _r in self._results if _r.ok)
        self._set_status(f"OK: {ok_count}/{self._validation_total}")
        self.after(30, self._poll_results)

    def _on_validation_complete(self) -> None:
        self.prog.stop()
        self.prog.grid_remove()
        self.btn_val.config(state="normal")
        self.btn_add.config(state="normal")
        self._refresh_ok_list()
        if self._ok_list:
            self.btn_best.config(state="normal")
            if len(self._ok_list) > 1:
                self.btn_next.config(state="normal")
        else:
            self.btn_best.config(state="disabled")
            self.btn_next.config(state="disabled")
        self._update_apply_button()
        ok_count = len(self._ok_list)
        self._set_status(f"Проверка завершена: OK {ok_count}/{self._validation_total}")
        if self._pending_action:
            self.after(10, self._complete_pending_action)

    def _refresh_ok_list(self) -> None:
        self._ok_list = sorted(
            [(proxy, result) for proxy, result in self._results if result.ok],
            key=lambda item: item[1].ping_ms or 1_000_000,
        )
        self._ok_index = 0

    # ------------------------------------------------------------------
    # Actions
    def _update_apply_button(self) -> None:
        self.btn_apply.config(state="normal" if self.tree.selection() else "disabled")

    def _get_selected(self) -> Optional[Tuple[Proxy, Optional[ValidationResult]]]:
        selection = self.tree.selection()
        if not selection:
            return None
        values = self.tree.item(selection[0], "values")
        try:
            port = int(values[2])
        except (ValueError, TypeError):
            return None
        proxy = Proxy(values[1], values[0], port, values[3] or None, None, values[4] or None)
        key = self._make_key(proxy)
        data = self._result_map.get(key)
        result = data[1] if data else None
        return proxy, result

    def _apply_selected(self) -> None:
        entry = self._get_selected()
        if not entry:
            return
        proxy, result = entry
        self._deliver_proxy(proxy, result)

    def _apply_first_ok(self) -> bool:
        if not self._ok_list:
            return False
        proxy, result = self._ok_list[0]
        self._ok_index = 1
        self._deliver_proxy(proxy, result)
        self.btn_next.config(state="normal" if len(self._ok_list) > 1 else "disabled")
        return True

    def _apply_next_ok(self) -> bool:
        if not self._ok_list or self._ok_index >= len(self._ok_list):
            return False
        proxy, result = self._ok_list[self._ok_index]
        self._ok_index += 1
        self._deliver_proxy(proxy, result)
        if self._ok_index >= len(self._ok_list):
            self.btn_next.config(state="disabled")
        return True

    def _deliver_proxy(self, proxy: Proxy, result: Optional[ValidationResult]) -> None:
        self._select_in_tree(proxy)
        self._set_status(
            f"Выбран {proxy.scheme.upper()} {proxy.host}:{proxy.port}" +
            (f" · {result.cc}" if result and result.cc else "")
        )
        if self.apply_callback:
            self.apply_callback(proxy, result)
    def _complete_pending_action(self) -> None:
        action = self._pending_action
        self._pending_action = None
        if action == "first":
            if not self._apply_first_ok():
                messagebox.showinfo("Proxy Lab", "Нет валидных прокси. Попробуйте обновить список.")
        elif action == "next":
            if not self._apply_next_ok():
                messagebox.showinfo("Proxy Lab", "Больше нет валидных прокси. Запустите парсинг снова.")

    def auto_pick_best(self) -> None:
        self._pending_action = "first"
        if not self._parsed:
            self._on_parse()
            self.after(100, self._await_validation)
            return
        if not self._results:
            self._begin_validation(auto=True)
            self.after(100, self._await_validation)
            return
        self._complete_pending_action()

    def auto_pick_next(self) -> None:
        if self._apply_next_ok():
            return
        self._pending_action = "first"
        self._on_parse()
        self.after(100, self._await_validation)

    def _await_validation(self) -> None:
        if self._pending_action:
            self.after(150, self._await_validation)

    def _on_add(self) -> None:
        ok_items: List[Proxy] = []
        for iid in self.tree.get_children():
            values = self.tree.item(iid, "values")
            if str(values[-1]).lower() != "yes":
                continue
            try:
                port = int(values[2])
            except (ValueError, TypeError):
                continue
            proxy = Proxy(values[1], values[0], port, values[3] or None, None, values[4] or None)
            ok_items.append(proxy)
        if not ok_items:
            messagebox.showwarning("Proxy Lab", "Нет валидных прокси для добавления.")
            return
        self.pool.append_to_csv(ok_items)
        messagebox.showinfo("Proxy Lab", f"Добавлено в пул: {len(ok_items)}")


