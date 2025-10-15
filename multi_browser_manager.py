from __future__ import annotations
import json
import os
import sys
import random
import tkinter as tk
from tkinter import messagebox, ttk
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
import uuid

try:
    import ttkbootstrap as tb
except Exception:  # pragma: no cover - fallback when ttkbootstrap missing
    tb = None

from proxy.models import Proxy
from proxy.pool import ProxyPool
from proxy.validate import ValidationResult, validate_proxy
from tools.logging_setup import app_root, get_logger
from ui.proxy_lab import ProxyLabFrame
from worker_chrome import launch_chrome, ensure_worker_chrome, detect_worker_chrome
from tools.lock_manager import ProfileLock


log = get_logger(__name__)
ROOT = app_root()
PROFILES_PATH = ROOT / "browser_profiles.json"


def _pid_exists(pid: Optional[int]) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@dataclass
class Profile:
    id: str
    name: str
    user_agent: str
    language: str
    timezone: str
    proxy_scheme: str = "http"
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    proxy_country: Optional[str] = None
    screen_width: int = 1920
    screen_height: int = 1080
    status: str = "offline"
    tags: str = ""
    os_name: str = "Windows"
    last_used: Optional[str] = None
    created: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        known = {field.name for field in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        payload = {k: v for k, v in data.items() if k in known}
        if not payload.get("id"):
            payload["id"] = uuid.uuid4().hex
        port = payload.get("proxy_port")
        if isinstance(port, str) and port.isdigit():
            payload["proxy_port"] = int(port)
        elif not isinstance(port, int):
            payload["proxy_port"] = None
        scheme = payload.get("proxy_scheme")
        if isinstance(scheme, str):
            payload["proxy_scheme"] = scheme.lower() or "http"
        for dim in ("screen_width", "screen_height"):
            val = payload.get(dim)
            if isinstance(val, str) and val.isdigit():
                payload[dim] = int(val)
            elif not isinstance(val, int):
                payload[dim] = 1920 if dim == 'screen_width' else 1080
        if not isinstance(payload.get("status"), str):
            payload["status"] = "offline"
        if not isinstance(payload.get("tags"), str):
            payload["tags"] = ""
        os_name = payload.get("os_name")
        if not isinstance(os_name, str) or not os_name.strip():
            payload["os_name"] = "Windows"
        return cls(**payload)

    def to_proxy(self) -> Optional[Proxy]:
        if self.proxy_host and self.proxy_port:
            return Proxy(
                scheme=(self.proxy_scheme or "http").lower(),
                host=self.proxy_host,
                port=int(self.proxy_port),
                username=self.proxy_username,
                password=self.proxy_password,
                country=self.proxy_country,
            )
        return None

    def update_proxy(self, proxy: Proxy) -> None:
        self.proxy_scheme = proxy.scheme.lower()
        self.proxy_host = proxy.host
        self.proxy_port = int(proxy.port)
        self.proxy_username = proxy.username
        self.proxy_password = proxy.password
        self.proxy_country = proxy.country
        self.touch()

    def touch(self) -> None:
        self.updated = datetime.utcnow().isoformat()


class ProfileStore:
    def __init__(self, path: Path):
        self.path = path
        if not path.exists():
            path.write_text("[]", encoding="utf-8")

    def load(self) -> List[Profile]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8") or "[]")
            return [Profile.from_dict(row) for row in data]
        except Exception as exc:
            log.error("Failed to load profiles: %s", exc)
            messagebox.showerror("AiChrome", f"Не удалось загрузить профили: {exc}")
            return []

    def save(self, profiles: List[Profile]) -> None:
        try:
            payload = [asdict(p) for p in profiles]
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.error("Failed to save profiles: %s", exc)
            messagebox.showerror("AiChrome", f"Не удалось сохранить профили: {exc}")


class ProfileDialog:
    def __init__(self, master: tk.Misc, profile: Optional[Profile] = None):
        self.master = master
        self.profile = profile
        self.result: Optional[Profile] = None

        self.top = tk.Toplevel(master)
        self.top.title("AiChrome — профиль")
        self.top.geometry("700x900")
        self.top.transient(master)
        self.top.grab_set()
        self.top.resizable(True, True)
        
        # Устанавливаем иконку для диалога
        try:
            icon_path = ROOT / "aichrome.ico"
            if icon_path.exists():
                self.top.iconbitmap(str(icon_path))
        except Exception:
            pass

        container = ttk.Frame(self.top, padding=12)
        container.pack(fill="both", expand=True)

        self._build_form(container)
        self._populate_fields(profile)
        if profile is None:
            self.generate_random_profile()

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(12, 0))
        ttk.Button(btn_frame, text="Отмена", command=self.top.destroy).pack(side="right")
        ttk.Button(btn_frame, text="ОК", command=self._on_ok).pack(side="right", padx=(0, 8))

        self.top.protocol("WM_DELETE_WINDOW", self.top.destroy)
        self.top.wait_window()

    def _build_form(self, parent: ttk.Frame) -> None:
        main = ttk.LabelFrame(parent, text="Профиль", padding=10)
        main.pack(fill="x")

        ttk.Label(main, text="Название:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        _name_entry = ttk.Entry(main, textvariable=self.name_var, width=40)
        _name_entry.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self._attach_context_menu(_name_entry)

        ttk.Label(main, text="User-Agent:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.ua_var = tk.StringVar()
        ua_row = ttk.Frame(main)
        ua_row.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        _ua_entry = ttk.Entry(ua_row, textvariable=self.ua_var)
        _ua_entry.pack(side="left", fill="x", expand=True)
        self._attach_context_menu(_ua_entry)
        ttk.Button(ua_row, text="Случайный", command=self.generate_random_ua).pack(side="left", padx=(6, 0))

        ttk.Label(main, text="Язык (Accept-Language):").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.lang_var = tk.StringVar(value="en-US")
        lang_row = ttk.Frame(main)
        lang_row.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        _lang_entry = ttk.Entry(lang_row, textvariable=self.lang_var)
        _lang_entry.pack(side="left", fill="x", expand=True)
        self._attach_context_menu(_lang_entry)
        ttk.Button(lang_row, text="Случайный", command=self.generate_random_language).pack(side="left", padx=(6, 0))

        ttk.Label(main, text="Часовой пояс (TZ):").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.tz_var = tk.StringVar(value="UTC")
        tz_row = ttk.Frame(main)
        tz_row.grid(row=3, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        _tz_entry = ttk.Entry(tz_row, textvariable=self.tz_var)
        _tz_entry.pack(side="left", fill="x", expand=True)
        self._attach_context_menu(_tz_entry)
        ttk.Button(tz_row, text="Случайный", command=self.generate_random_timezone).pack(side="left", padx=(6, 0))

        ttk.Label(main, text="Операционная система:").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.os_var = tk.StringVar(value="Windows")
        ttk.Combobox(
            main,
            textvariable=self.os_var,
            values=("Windows", "macOS", "Linux"),
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        ttk.Label(main, text="Теги:").grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.tags_var = tk.StringVar()
        _tags_entry = ttk.Entry(main, textvariable=self.tags_var)
        _tags_entry.grid(row=5, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        self._attach_context_menu(_tags_entry)

        display = ttk.LabelFrame(parent, text="Отпечаток", padding=10)
        display.pack(fill="x", pady=(12, 0))
        ttk.Label(display, text="Разрешение:").grid(row=0, column=0, sticky="w")
        self.screen_width_var = tk.StringVar(value="1920")
        self.screen_height_var = tk.StringVar(value="1080")
        res_row = ttk.Frame(display)
        res_row.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        _sw_entry = ttk.Entry(res_row, textvariable=self.screen_width_var, width=8)
        _sw_entry.pack(side="left")
        self._attach_context_menu(_sw_entry)
        ttk.Label(res_row, text="×").pack(side="left", padx=4)
        _sh_entry = ttk.Entry(res_row, textvariable=self.screen_height_var, width=8)
        _sh_entry.pack(side="left")
        self._attach_context_menu(_sh_entry)
        ttk.Button(res_row, text="Случайное", command=self.generate_random_resolution).pack(side="left", padx=(6, 0))

        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True, pady=(12, 0))

        proxy_tab = ttk.Frame(notebook)
        notebook.add(proxy_tab, text="Прокси")

        ttk.Label(proxy_tab, text="Тип (http/socks4/socks5):").grid(row=0, column=0, sticky="w")
        self.scheme_var = tk.StringVar(value="http")
        ttk.Combobox(proxy_tab, textvariable=self.scheme_var, values=("http", "socks4", "socks5"), state="readonly").grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Label(proxy_tab, text="Страна (ISO)").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.country_var = tk.StringVar(value="US")
        _country_entry = ttk.Entry(proxy_tab, textvariable=self.country_var)
        _country_entry.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        self._attach_context_menu(_country_entry)

        ttk.Label(proxy_tab, text="Хост").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.host_var = tk.StringVar()
        _host_entry = ttk.Entry(proxy_tab, textvariable=self.host_var)
        _host_entry.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        self._attach_context_menu(_host_entry)

        ttk.Label(proxy_tab, text="Порт").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.port_var = tk.StringVar()
        _port_entry = ttk.Entry(proxy_tab, textvariable=self.port_var)
        _port_entry.grid(row=3, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        self._attach_context_menu(_port_entry)

        ttk.Label(proxy_tab, text="Логин").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.user_var = tk.StringVar()
        _user_entry = ttk.Entry(proxy_tab, textvariable=self.user_var)
        _user_entry.grid(row=4, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        self._attach_context_menu(_user_entry)

        ttk.Label(proxy_tab, text="Пароль").grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.pass_var = tk.StringVar()
        _pass_entry = ttk.Entry(proxy_tab, textvariable=self.pass_var, show="*")
        _pass_entry.grid(row=5, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        self._attach_context_menu(_pass_entry)

        proxy_tab.columnconfigure(1, weight=1)
        main.columnconfigure(1, weight=1)

        actions = ttk.Frame(proxy_tab)
        actions.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(actions, text="🔌 Автопрокси", command=self._lab_auto_best).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="⟳ Следующий", command=self._lab_auto_next).grid(row=0, column=1, sticky="w", padx=(6, 0))

        lab_tab = ttk.Frame(notebook)
        notebook.add(lab_tab, text="Proxy Lab")
        self.lab_frame = ProxyLabFrame(
            lab_tab,
            apply_callback=self._apply_proxy_from_lab,
            scheme_getter=lambda: self.scheme_var.get(),
            country_getter=lambda: self.country_var.get(),
        )
        self.lab_frame.pack(fill="both", expand=True, padx=6, pady=6)

        ttk.Button(parent, text="🎲 Случайные настройки", command=self.generate_random_profile).pack(fill="x", padx=6, pady=(8, 0))

        def _sync_lab(*_):
            self.lab_frame.sync_with_parent(self.scheme_var.get(), self.country_var.get())

        _sync_lab()
        self.scheme_var.trace_add("write", _sync_lab)
        self.country_var.trace_add("write", _sync_lab)

    # ---------------------------------------------------------------
    # Context menu for Entry widgets (Cut/Copy/Paste/Select All)
    def _attach_context_menu(self, widget: tk.Widget) -> None:
        # Context menu
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Вырезать (Ctrl+X)", command=lambda w=widget: self._do_cut(w))
        menu.add_command(label="Копировать (Ctrl+C)", command=lambda w=widget: self._do_copy(w))
        menu.add_command(label="Вставить (Ctrl+V)", command=lambda w=widget: self._do_paste(w))
        menu.add_separator()
        menu.add_command(label="Выделить всё (Ctrl+A)", command=lambda w=widget: self._do_select_all(w))

        def show_menu(event: tk.Event) -> None:
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", show_menu)
    
    def _do_copy(self, widget):
        """Copy selected text to clipboard"""
        try:
            if isinstance(widget, (tk.Entry, ttk.Entry)):
                if widget.selection_present():
                    text = widget.selection_get()
                    self.top.clipboard_clear()
                    self.top.clipboard_append(text)
            elif isinstance(widget, tk.Text):
                text = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
                self.top.clipboard_clear()
                self.top.clipboard_append(text)
        except (tk.TclError, AttributeError):
            pass
    
    def _do_cut(self, widget):
        """Cut selected text to clipboard"""
        try:
            if isinstance(widget, (tk.Entry, ttk.Entry)):
                if widget.selection_present():
                    text = widget.selection_get()
                    self.top.clipboard_clear()
                    self.top.clipboard_append(text)
                    # Delete selected text - use anchor and selection end
                    first = widget.index(tk.ANCHOR)
                    last = widget.index(tk.INSERT)
                    if first > last:
                        first, last = last, first
                    widget.delete(first, last)
            elif isinstance(widget, tk.Text):
                text = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
                self.top.clipboard_clear()
                self.top.clipboard_append(text)
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except (tk.TclError, AttributeError):
            pass
    
    def _do_paste(self, widget):
        """Paste text from clipboard"""
        try:
            text = self.top.clipboard_get()
            if isinstance(widget, (tk.Entry, ttk.Entry)):
                # Get current cursor position
                pos = widget.index(tk.INSERT)
                # Delete selected text if any
                try:
                    if widget.selection_present():
                        widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                        pos = widget.index(tk.INSERT)
                except tk.TclError:
                    pass
                # Insert text at cursor position
                widget.insert(pos, text)
            elif isinstance(widget, tk.Text):
                try:
                    if widget.tag_ranges(tk.SEL):
                        widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                except tk.TclError:
                    pass
                widget.insert(tk.INSERT, text)
        except (tk.TclError, AttributeError) as e:
            print(f"Paste error: {e}")
            pass
    
    def _do_select_all(self, widget):
        """Select all text"""
        try:
            if isinstance(widget, (tk.Entry, ttk.Entry)):
                widget.selection_range(0, tk.END)
                widget.icursor(tk.END)
            elif isinstance(widget, tk.Text):
                widget.tag_add(tk.SEL, "1.0", tk.END)
                widget.mark_set(tk.INSERT, "1.0")
        except tk.TclError:
            pass

    def _on_ok(self) -> None:
        """Сохраняет профиль и закрывает окно"""
        try:
            name = self.name_var.get().strip()
            if not name:
                messagebox.showerror("AiChrome", "Введите название профиля")
                return
            
            # Создаем или обновляем профиль
            if self.profile:
                # Обновляем существующий
                self.profile.name = name
                self.profile.user_agent = self.ua_var.get().strip()
                self.profile.language = self.lang_var.get().strip()
                self.profile.timezone = self.tz_var.get().strip()
                self.profile.screen_width = int(self.screen_width_var.get() or "1920")
                self.profile.screen_height = int(self.screen_height_var.get() or "1080")
                self.profile.proxy_scheme = self.scheme_var.get()
                self.profile.proxy_country = self.country_var.get().strip()
                self.profile.proxy_host = self.host_var.get().strip()
                self.profile.proxy_port = int(self.port_var.get()) if self.port_var.get().strip() else None
                self.profile.proxy_username = self.user_var.get().strip()
                self.profile.proxy_password = self.pass_var.get().strip()
                self.profile.tags = self.tags_var.get().strip()
                self.profile.os_name = self.os_var.get().strip() or "Windows"
                self.profile.updated = datetime.now().isoformat()
                self.result = self.profile
            else:
                # Создаем новый
                self.result = Profile(
                    id=str(uuid.uuid4()),
                    name=name,
                    user_agent=self.ua_var.get().strip(),
                    language=self.lang_var.get().strip(),
                    timezone=self.tz_var.get().strip(),
                    screen_width=int(self.screen_width_var.get() or "1920"),
                    screen_height=int(self.screen_height_var.get() or "1080"),
                    proxy_scheme=self.scheme_var.get(),
                    proxy_country=self.country_var.get().strip(),
                    proxy_host=self.host_var.get().strip(),
                    proxy_port=int(self.port_var.get()) if self.port_var.get().strip() else None,
                    proxy_username=self.user_var.get().strip(),
                    proxy_password=self.pass_var.get().strip(),
                    tags=self.tags_var.get().strip(),
                    os_name=self.os_var.get().strip() or "Windows",
                    created=datetime.now().isoformat(),
                    updated=datetime.now().isoformat()
                )
                self.result.status = "offline"
                self.result.last_used = None
            
            self.top.destroy()
        except ValueError as e:
            messagebox.showerror("AiChrome", f"Ошибка в данных: {e}")
        except Exception as e:
            messagebox.showerror("AiChrome", f"Ошибка сохранения: {e}")

    def _populate_fields(self, profile: Optional[Profile]) -> None:
        if not profile:
            return
        self.name_var.set(profile.name)
        self.ua_var.set(profile.user_agent)
        self.lang_var.set(profile.language)
        self.tz_var.set(profile.timezone)
        self.scheme_var.set((profile.proxy_scheme or "http").lower())
        if profile.proxy_country:
            self.country_var.set(profile.proxy_country)
        if profile.proxy_host:
            self.host_var.set(profile.proxy_host)
        if profile.proxy_port:
            self.port_var.set(str(profile.proxy_port))
        if profile.proxy_username:
            self.user_var.set(profile.proxy_username)
        if profile.proxy_password:
            self.pass_var.set(profile.proxy_password)
        self.screen_width_var.set(str(profile.screen_width))
        self.screen_height_var.set(str(profile.screen_height))
        self.os_var.set(profile.os_name or "Windows")
        self.tags_var.set(profile.tags or "")

    def _apply_proxy_from_lab(self, proxy: Proxy, result: Optional[ValidationResult]) -> None:
        self.scheme_var.set(proxy.scheme.lower())
        self.host_var.set(proxy.host)
        self.port_var.set(str(proxy.port))
        self.user_var.set(proxy.username or "")
        self.pass_var.set(proxy.password or "")
        if result and result.cc:
            self.country_var.set(result.cc)
        elif proxy.country:
            self.country_var.set(proxy.country)
        self.lab_frame.sync_with_parent(self.scheme_var.get(), self.country_var.get())

    def _lab_auto_best(self) -> None:
        try:
            self.lab_frame.sync_with_parent(self.scheme_var.get(), self.country_var.get())
            self.lab_frame.auto_pick_best()
        except Exception as e:
            messagebox.showerror("AiChrome", f"Ошибка автопрокси: {e}")

    def _lab_auto_next(self) -> None:
        try:
            self.lab_frame.sync_with_parent(self.scheme_var.get(), self.country_var.get())
            self.lab_frame.auto_pick_next()
        except Exception as e:
            messagebox.showerror("AiChrome", f"Ошибка следующего прокси: {e}")

    def generate_random_ua(self) -> None:
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 12.6; rv:125.0) Gecko/20100101 Firefox/125.0",
        ]
        self.ua_var.set(random.choice(agents))

    def generate_random_resolution(self) -> None:
        presets = [(1920, 1080), (2560, 1440), (1680, 1050), (1600, 900), (1366, 768), (1440, 900), (1536, 864), (1280, 720)]
        width, height = random.choice(presets)
        self.screen_width_var.set(str(width))
        self.screen_height_var.set(str(height))

    def generate_random_timezone(self) -> None:
        zones = [
            "America/New_York",
            "America/Los_Angeles",
            "Europe/Berlin",
            "Europe/Paris",
            "Europe/Moscow",
            "Asia/Tokyo",
            "Asia/Singapore",
            "Australia/Sydney",
            "America/Sao_Paulo",
        ]
        self.tz_var.set(random.choice(zones))

    def generate_random_language(self) -> None:
        langs = ["en-US", "en-GB", "de-DE", "fr-FR", "es-ES", "ru-RU", "tr-TR", "zh-CN", "pt-BR"]
        self.lang_var.set(random.choice(langs))

    def generate_random_profile(self) -> None:
        self.generate_random_ua()
        self.generate_random_resolution()
        self.generate_random_timezone()
        self.generate_random_language()
        self.os_var.set(random.choice(["Windows", "macOS", "Linux"]))
        self.tags_var.set("")



class BrowserManagerApp:
    def __init__(self) -> None:
        if tb:
            self.root = tb.Window(themename="flatly")
        else:
            self.root = tk.Tk()
        self.root.title("AiChrome — менеджер профилей")
        self.root.geometry("960x640")
        
        # Устанавливаем иконку приложения
        try:
            icon_path = ROOT / "aichrome.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass  # Игнорируем ошибки с иконкой

        self.store = ProfileStore(PROFILES_PATH)
        self.profiles: List[Profile] = self.store.load()
        self.pool = ProxyPool()

        self.status_var = tk.StringVar(value="Готово")

        self._build_ui()
        self._refresh_tree()
        self._start_status_timer()

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="Создать", command=self.create_profile).pack(side="left")
        ttk.Button(toolbar, text="Редактировать", command=self.edit_profile).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Клонировать", command=self.clone_profile).pack(side="left", padx=(6, 0))
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(toolbar, text="Автопрокси", command=self.autoproxy_selected).pack(side="left")
        ttk.Button(toolbar, text="Self-Test", command=self.self_test_selected).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Запустить", command=self.launch_selected).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Установить рабочий Chrome", command=self.install_worker_chrome).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Обновить", command=self.reload_profiles).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Удалить", command=self.delete_profile).pack(side="right")

        columns = ("name", "status", "tags", "os", "proxy", "created", "last_used")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=18)
        headers = {
            "name": "Профиль",
            "status": "Статус",
            "tags": "Теги",
            "os": "OS",
            "proxy": "Прокси",
            "created": "Создан",
            "last_used": "Последнее использование",
        }
        widths = {
            "name": 200,
            "status": 90,
            "tags": 130,
            "os": 90,
            "proxy": 220,
            "created": 140,
            "last_used": 160,
        }
        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        status_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        status_frame.pack(fill="x")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left")

    def _refresh_tree(self, preserve_selection: Optional[tuple[str, ...]] = None) -> None:
        selected = preserve_selection or self.tree.selection()

        for item in self.tree.get_children():
            self.tree.delete(item)

        changed = False
        running = 0
        for profile in self.profiles:
            status = self._determine_profile_status(profile)
            if profile.status != status:
                profile.status = status
                changed = True
            if status == "running":
                running += 1

            proxy_display = ""
            if profile.proxy_host and profile.proxy_port:
                proxy_display = f"{profile.proxy_scheme.upper()} {profile.proxy_host}:{profile.proxy_port}"

            created = self._human_dt(profile.created)
            last_used = self._human_dt(profile.last_used)

            self.tree.insert(
                "",
                "end",
                iid=profile.id,
                values=(
                    profile.name,
                    status,
                    profile.tags or "",
                    profile.os_name,
                    proxy_display,
                    created,
                    last_used,
                ),
            )

        for iid in selected:
            if self.tree.exists(iid):
                self.tree.selection_add(iid)

        if changed:
            self.store.save(self.profiles)

        self.status_var.set(f"Профилей: {len(self.profiles)} · Активных: {running}")

    def _start_status_timer(self) -> None:
        self.root.after(3000, self._status_tick)

    def _status_tick(self) -> None:
        try:
            selection = self.tree.selection()
            self._refresh_tree(preserve_selection=selection)
        finally:
            self.root.after(3000, self._status_tick)

    def _save_profiles(self) -> None:
        self.store.save(self.profiles)
        self._refresh_tree()

    def _human_dt(self, value: Optional[str]) -> str:
        if not value:
            return ""
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return value or ""

    def _determine_profile_status(self, profile: Profile) -> str:
        lock = ProfileLock(ROOT / "profiles" / profile.id)
        data = lock.read()
        pid = data.get("chrome_pid")
        if _pid_exists(pid):
            return "running"
        lock.release_if_dead()
        return "offline"

    def create_profile(self) -> None:
        dialog = ProfileDialog(self.root)
        if dialog.result:
            self.profiles.append(dialog.result)
            self._save_profiles()
            self.status_var.set(f"Создан профиль {dialog.result.name}")

    def edit_profile(self) -> None:
        profile = self._get_selected_profile()
        if not profile:
            messagebox.showwarning("AiChrome", "Выберите профиль")
            return
        dialog = ProfileDialog(self.root, profile)
        if dialog.result:
            for idx, existing in enumerate(self.profiles):
                if existing.id == dialog.result.id:
                    self.profiles[idx] = dialog.result
                    break
            self._save_profiles()
            self.status_var.set(f"Обновлён профиль {dialog.result.name}")

    def delete_profile(self) -> None:
        profile = self._get_selected_profile()
        if not profile:
            messagebox.showwarning("AiChrome", "Выберите профиль")
            return
        if not messagebox.askyesno("AiChrome", f"Удалить профиль '{profile.name}'?"):
            return
        self.profiles = [p for p in self.profiles if p.id != profile.id]
        # удалить папку профиля
        prof_dir = ROOT / "profiles" / profile.id
        if prof_dir.exists():
            try:
                import shutil
                shutil.rmtree(prof_dir, ignore_errors=True)
            except Exception as exc:
                log.warning("Failed to remove profile dir: %s", exc)
        self._save_profiles()
        self.status_var.set(f"Удалён профиль {profile.name}")

    def clone_profile(self) -> None:
        profile = self._get_selected_profile()
        if not profile:
            messagebox.showwarning("AiChrome", "Выберите профиль для клонирования")
            return
        clone = Profile.from_dict(asdict(profile))
        clone.id = uuid.uuid4().hex
        clone.name = f"{profile.name}_copy"
        now = datetime.utcnow().isoformat()
        clone.created = now
        clone.updated = now
        clone.status = "offline"
        clone.last_used = None
        self.profiles.append(clone)
        self._save_profiles()
        self.status_var.set(f"Скопирован профиль {clone.name}")

    def reload_profiles(self) -> None:
        self.profiles = self.store.load()
        self._refresh_tree()
        self.status_var.set("Профили обновлены")

    def install_worker_chrome(self) -> None:
        try:
            existing = detect_worker_chrome()
            if existing:
                if not messagebox.askyesno(
                    "AiChrome",
                    f"Найден рабочий Chrome:\n{existing}\nПерезаменить на свежую версию?",
                ):
                    return

            def prompt(title: str, text: str) -> bool:
                return messagebox.askyesno(title, text)

            path = ensure_worker_chrome(auto=False, ask=prompt)
            if path:
                messagebox.showinfo("AiChrome", f"Рабочий Chrome готов:\n{path}")
            else:
                messagebox.showinfo("AiChrome", "Установка отменена")
        except Exception as exc:
            log.error("Worker chrome install failed: %s", exc)
            messagebox.showerror("AiChrome", f"Не удалось установить рабочий Chrome: {exc}")

    def autoproxy_selected(self) -> None:
        profile = self._get_selected_profile()
        if not profile:
            messagebox.showwarning("AiChrome", "Выберите профиль")
            return
        try:
            proxy, source, result = self._autoproxy_for_profile(profile)
        except Exception as exc:
            messagebox.showerror("AiChrome", str(exc))
            return
        profile.update_proxy(proxy)
        self._save_profiles()
        details = f"{proxy.scheme} {proxy.host}:{proxy.port}"
        if result and result.cc:
            details += f" · {result.cc}"
        messagebox.showinfo("AiChrome", f"Подключён прокси ({source}):\n{details}")
        self.status_var.set(f"Прокси обновлён: {details}")

    def self_test_selected(self) -> None:
        profile = self._get_selected_profile()
        if not profile:
            messagebox.showwarning("AiChrome", "Выберите профиль")
            return
        proxy = profile.to_proxy()
        info: Optional[ValidationResult] = None
        if not proxy:
            try:
                proxy, _, info = self._autoproxy_for_profile(profile)
            except Exception as exc:
                messagebox.showerror("AiChrome", str(exc))
                return
            profile.update_proxy(proxy)
            self._save_profiles()
        if proxy and not info:
            info = validate_proxy(proxy)
        if not info:
            messagebox.showerror("AiChrome", "Не удалось выполнить Self-Test")
            return
        if info.ok:
            msg = f"✅ Прокси активен\nIP: {info.ip or 'n/a'}\nСтрана: {info.country or info.cc or 'n/a'}\nPing: {info.ping_ms or '—'} ms"
            messagebox.showinfo("AiChrome", msg)
            self.status_var.set(f"Self-Test: {info.ip or 'n/a'} ({info.cc or info.country or 'n/a'})")
        else:
            messagebox.showwarning("AiChrome", f"Прокси не отвечает: {info.error}")

    def launch_selected(self) -> None:
        profile = self._get_selected_profile()
        if not profile:
            messagebox.showwarning("AiChrome", "Выберите профиль")
            return
        proxy = profile.to_proxy()
        info: Optional[ValidationResult] = None
        source = "manual"
        if not proxy:
            try:
                proxy, source, info = self._autoproxy_for_profile(profile)
            except Exception as exc:
                messagebox.showerror("AiChrome", str(exc))
                return
            profile.update_proxy(proxy)
            self._save_profiles()
        log.info("Launching profile %s with proxy %s", profile.name, proxy.host if proxy else "direct")
        try:
            flags = [f"--window-size={profile.screen_width},{profile.screen_height}"]
            pid = launch_chrome(
                profile_id=profile.id,
                user_agent=profile.user_agent,
                lang=profile.language,
                tz=profile.timezone,
                proxy=proxy,
                extra_flags=flags,
                allow_system_chrome=True,
            )
        except Exception as exc:
            log.error("Failed to launch Chrome: %s", exc)
            messagebox.showerror("AiChrome", f"Не удалось запустить Chrome: {exc}")
            return
        details = f"PID {pid}"
        if proxy:
            details += f" — {proxy.scheme} {proxy.host}:{proxy.port} ({source})"
        profile.status = "running"
        profile.last_used = datetime.utcnow().isoformat()
        profile.touch()
        self._save_profiles()
        self.status_var.set(f"Chrome запущен: {details}")
        messagebox.showinfo("AiChrome", f"Chrome запущен\n{details}")

    def _autoproxy_for_profile(self, profile: Profile) -> Tuple[Proxy, str, Optional[ValidationResult]]:
        sticky = self.pool.get_sticky(profile.id)
        if sticky:
            log.info("Using sticky proxy for %s", profile.id)
            return sticky, "sticky", None
        scheme = profile.proxy_scheme or "http"
        proxy, result = self.pool.select_live(profile.proxy_country, scheme)
        if not proxy:
            raise RuntimeError("Не найден живой прокси: заполните пул через Proxy Lab")
        self.pool.set_sticky(profile.id, proxy)
        return proxy, "fresh", result

    def _get_selected_profile(self) -> Optional[Profile]:
        selection = self.tree.selection()
        if not selection:
            return None
        pid = selection[0]
        for profile in self.profiles:
            if profile.id == pid:
                return profile
        return None

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = BrowserManagerApp()
    app.run()


if __name__ == "__main__":
    main()
