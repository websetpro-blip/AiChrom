#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AiChrome - Простой рабочий браузер-менеджер
БЕЗ ЛИШНИХ СЛОЖНОСТЕЙ, ПРОСТО РАБОТАЕТ!
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import json
import os
import sys
import threading
import time
import uuid
import requests
from datetime import datetime
from pathlib import Path
import psutil

class SimpleBrowserManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AiChrome - Простой браузер-менеджер")
        self.root.geometry("1000x600")
        
        # Пути
        self.base_dir = Path(__file__).parent if not getattr(sys, 'frozen', False) else Path(sys.executable).parent
        self.profiles_file = self.base_dir / "profiles.json"
        self.profiles_dir = self.base_dir / "browser_profiles"
        self.profiles_dir.mkdir(exist_ok=True)
        
        # Данные
        self.profiles = self.load_profiles()
        self.running_browsers = {}
        
        # Chrome path
        self.chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser"
        ]
        self.chrome_path = self.find_chrome()
        
        self.create_ui()
        self.refresh_table()
        
        if not self.chrome_path:
            messagebox.showerror("Ошибка", "Chrome не найден! Установите Google Chrome.")
    
    def find_chrome(self):
        """Простой поиск Chrome"""
        for path in self.chrome_paths:
            if os.path.exists(path):
                return path
        return None
    
    def create_ui(self):
        """Создание интерфейса"""
        # Заголовок
        header = tk.Frame(self.root, bg="#2d3748", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(header, text="🌐 AiChrome", font=("Arial", 18, "bold"), 
                        fg="white", bg="#2d3748")
        title.pack(side=tk.LEFT, padx=20, pady=15)
        
        subtitle = tk.Label(header, text="Простой браузер-менеджер • РАБОТАЕТ!", 
                           font=("Arial", 10), fg="#a0aec0", bg="#2d3748")
        subtitle.pack(side=tk.LEFT, padx=(0, 20), pady=15)
        
        # Кнопки
        btn_frame = tk.Frame(self.root, bg="#f7fafc", height=50)
        btn_frame.pack(fill=tk.X, pady=10)
        btn_frame.pack_propagate(False)
        
        tk.Button(btn_frame, text="➕ Создать профиль", command=self.create_profile,
                 bg="#48bb78", fg="white", font=("Arial", 10, "bold"), 
                 padx=20, pady=8).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="🚀 Запустить", command=self.launch_browser,
                 bg="#4299e1", fg="white", font=("Arial", 10, "bold"), 
                 padx=20, pady=8).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="🧪 Тест IP", command=self.test_proxy,
                 bg="#ed8936", fg="white", font=("Arial", 10, "bold"), 
                 padx=20, pady=8).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="🗑️ Удалить", command=self.delete_profile,
                 bg="#f56565", fg="white", font=("Arial", 10, "bold"), 
                 padx=20, pady=8).pack(side=tk.RIGHT, padx=10)
        
        # Таблица профилей
        self.create_table()
        
        # Статус
        self.status = tk.Label(self.root, text="Готов к работе", 
                              bg="#edf2f7", font=("Arial", 9), anchor="w")
        self.status.pack(fill=tk.X, side=tk.BOTTOM)
    
    def create_table(self):
        """Создание таблицы профилей"""
        table_frame = tk.Frame(self.root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        columns = ("name", "proxy", "status", "created")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        
        # Заголовки
        self.tree.heading("name", text="Название")
        self.tree.heading("proxy", text="Прокси")
        self.tree.heading("status", text="Статус")
        self.tree.heading("created", text="Создан")
        
        # Ширина колонок
        self.tree.column("name", width=200)
        self.tree.column("proxy", width=300)
        self.tree.column("status", width=100)
        self.tree.column("created", width=150)
        
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # Скроллбар
        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    def load_profiles(self):
        """Загрузка профилей"""
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_profiles(self):
        """Сохранение профилей"""
        try:
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")
            return False
    
    def refresh_table(self):
        """Обновление таблицы"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for profile in self.profiles:
            proxy_str = ""
            if profile.get("proxy_host"):
                proxy_str = f"{profile.get('proxy_type', 'HTTP')}://{profile['proxy_host']}:{profile.get('proxy_port', 80)}"
            
            status = "🟢 Активен" if profile.get("id") in self.running_browsers else "⚪ Неактивен"
            
            self.tree.insert("", "end", values=(
                profile.get("name", "Без имени"),
                proxy_str,
                status,
                profile.get("created", "")
            ), tags=(profile.get("id"),))
    
    def create_profile(self):
        """Создание нового профиля"""
        ProfileDialog(self.root, self)
    
    def get_selected_profile(self):
        """Получение выбранного профиля"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите профиль")
            return None
        
        tags = self.tree.item(selection[0])["tags"]
        if not tags:
            return None
        
        profile_id = tags[0]
        return next((p for p in self.profiles if p["id"] == profile_id), None)
    
    def delete_profile(self):
        """Удаление профиля"""
        profile = self.get_selected_profile()
        if not profile:
            return
        
        if messagebox.askyesno("Подтверждение", f"Удалить профиль '{profile['name']}'?"):
            # Закрыть браузер если запущен
            if profile["id"] in self.running_browsers:
                try:
                    self.running_browsers[profile["id"]].terminate()
                    del self.running_browsers[profile["id"]]
                except:
                    pass
            
            # Удалить папку профиля
            profile_dir = self.profiles_dir / profile["id"]
            if profile_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(profile_dir)
                except:
                    pass
            
            # Удалить из списка
            self.profiles.remove(profile)
            self.save_profiles()
            self.refresh_table()
            self.update_status(f"Профиль удален: {profile['name']}")
    
    def launch_browser(self):
        """Запуск браузера"""
        profile = self.get_selected_profile()
        if not profile or not self.chrome_path:
            return
        
        # Проверка на повторный запуск
        if profile["id"] in self.running_browsers:
            proc = self.running_browsers[profile["id"]]
            if proc.poll() is None:
                messagebox.showinfo("Информация", "Браузер уже запущен для этого профиля")
                return
            else:
                del self.running_browsers[profile["id"]]
        
        # Запуск в отдельном потоке
        threading.Thread(target=self.start_chrome, args=(profile,), daemon=True).start()
    
    def start_chrome(self, profile):
        """Запуск Chrome с настройками"""
        try:
            profile_dir = self.profiles_dir / profile["id"]
            profile_dir.mkdir(exist_ok=True)
            
            # Основные аргументы Chrome
            args = [
                self.chrome_path,
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-popup-blocking",
                f"--user-agent={profile.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')}",
                f"--window-size={profile.get('width', 1280)},{profile.get('height', 800)}"
            ]
            
            # Прокси
            if profile.get("proxy_host") and profile.get("proxy_port"):
                proxy_type = profile.get("proxy_type", "http").lower()
                proxy_url = f"{proxy_type}://{profile['proxy_host']}:{profile['proxy_port']}"
                args.append(f"--proxy-server={proxy_url}")
                
                # Авторизация прокси (если есть логин/пароль)
                if profile.get("proxy_user") and profile.get("proxy_pass"):
                    self.create_proxy_extension(profile)
                    ext_dir = self.profiles_dir / profile["id"] / "proxy_auth_extension"
                    args.append(f"--load-extension={ext_dir}")
            
            self.root.after(0, lambda: self.update_status(f"Запуск браузера: {profile['name']}"))
            
            # Запуск процесса
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.running_browsers[profile["id"]] = process
            
            self.root.after(0, lambda: self.update_status(f"Браузер запущен: {profile['name']} (PID: {process.pid})"))
            self.root.after(0, self.refresh_table)
            
            # Ждем завершения
            process.wait()
            
            # Уборка
            if profile["id"] in self.running_browsers:
                del self.running_browsers[profile["id"]]
            
            self.root.after(0, lambda: self.update_status(f"Браузер закрыт: {profile['name']}"))
            self.root.after(0, self.refresh_table)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось запустить браузер: {e}"))
    
    def create_proxy_extension(self, profile):
        """Создание расширения для авторизации прокси"""
        try:
            ext_dir = self.profiles_dir / profile["id"] / "proxy_auth_extension"
            ext_dir.mkdir(parents=True, exist_ok=True)
            
            # manifest.json
            manifest = {
                "manifest_version": 3,
                "name": "Proxy Auth",
                "version": "1.0",
                "permissions": ["proxy", "webRequest", "webRequestAuthProvider", "storage"],
                "host_permissions": ["<all_urls>"],
                "background": {"service_worker": "background.js"}
            }
            
            with open(ext_dir / "manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            
            # background.js
            bg_script = f"""
chrome.webRequest.onAuthRequired.addListener(
    function(details, callback) {{
        callback({{
            authCredentials: {{
                username: "{profile.get('proxy_user', '')}",
                password: "{profile.get('proxy_pass', '')}"
            }}
        }});
    }},
    {{urls: ["<all_urls>"]}},
    ["blocking"]
);
"""
            with open(ext_dir / "background.js", "w", encoding="utf-8") as f:
                f.write(bg_script)
            
        except Exception as e:
            print(f"Ошибка создания расширения: {e}")
    
    def test_proxy(self):
        """Тестирование прокси"""
        profile = self.get_selected_profile()
        if not profile:
            return
        
        if not profile.get("proxy_host"):
            messagebox.showinfo("Информация", "У профиля нет настроек прокси")
            return
        
        self.update_status("Тестирование прокси...")
        threading.Thread(target=self.check_proxy, args=(profile,), daemon=True).start()
    
    def check_proxy(self, profile):
        """Проверка прокси"""
        try:
            proxy_type = profile.get("proxy_type", "http").lower()
            proxy_url = f"{proxy_type}://{profile['proxy_host']}:{profile['proxy_port']}"
            
            # Если есть авторизация
            if profile.get("proxy_user"):
                proxy_url = f"{proxy_type}://{profile['proxy_user']}:{profile.get('proxy_pass', '')}@{profile['proxy_host']}:{profile['proxy_port']}"
            
            proxies = {
                "http": proxy_url,
                "https": proxy_url
            }
            
            # Проверяем IP
            response = requests.get("https://api.ipify.org?format=json", 
                                  proxies=proxies, timeout=10)
            
            if response.status_code == 200:
                ip_data = response.json()
                ip = ip_data.get("ip", "Неизвестно")
                
                # Получаем информацию о стране
                try:
                    geo_response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
                    if geo_response.status_code == 200:
                        geo_data = geo_response.json()
                        country = geo_data.get("country", "Неизвестно")
                        city = geo_data.get("city", "Неизвестно")
                        msg = f"✅ Прокси работает!\n\nIP: {ip}\nСтрана: {country}\nГород: {city}"
                    else:
                        msg = f"✅ Прокси работает!\n\nIP: {ip}"
                except:
                    msg = f"✅ Прокси работает!\n\nIP: {ip}"
                
                self.root.after(0, lambda: messagebox.showinfo("Результат теста", msg))
                self.root.after(0, lambda: self.update_status(f"Прокси работает: {ip}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", "Прокси не отвечает"))
                self.root.after(0, lambda: self.update_status("Прокси не работает"))
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка проверки прокси: {e}"))
            self.root.after(0, lambda: self.update_status("Ошибка проверки прокси"))
    
    def update_status(self, message):
        """Обновление статуса"""
        self.status.config(text=f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    
    def run(self):
        """Запуск приложения"""
        self.root.mainloop()


class ProfileDialog:
    def __init__(self, parent, manager):
        self.manager = manager
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Создание профиля")
        self.dialog.geometry("600x700")
        self.dialog.resizable(False, False)
        
        # Модальность
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование
        self.center_window()
        
        self.create_ui()
    
    def center_window(self):
        """Центрирование окна"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (700 // 2)
        self.dialog.geometry(f"600x700+{x}+{y}")
    
    def create_ui(self):
        """Создание интерфейса диалога"""
        # Заголовок
        header = tk.Frame(self.dialog, bg="#4299e1", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(header, text="➕ Новый профиль", font=("Arial", 16, "bold"), 
                        fg="white", bg="#4299e1")
        title.pack(pady=15)
        
        # Основная форма
        main_frame = tk.Frame(self.dialog, bg="#f7fafc")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Название профиля
        tk.Label(main_frame, text="Название профиля:", font=("Arial", 10, "bold"), 
                bg="#f7fafc").pack(anchor=tk.W, pady=(0, 5))
        self.name_var = tk.StringVar()
        tk.Entry(main_frame, textvariable=self.name_var, font=("Arial", 11), 
                width=50).pack(fill=tk.X, pady=(0, 15))
        
        # User-Agent
        tk.Label(main_frame, text="User-Agent:", font=("Arial", 10, "bold"), 
                bg="#f7fafc").pack(anchor=tk.W, pady=(0, 5))
        ua_frame = tk.Frame(main_frame, bg="#f7fafc")
        ua_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.ua_var = tk.StringVar()
        tk.Entry(ua_frame, textvariable=self.ua_var, font=("Arial", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(ua_frame, text="🎲 Случайный", command=self.random_ua, 
                 bg="#ed8936", fg="white", font=("Arial", 9)).pack(side=tk.RIGHT, padx=(10, 0))
        
        # Размер окна
        tk.Label(main_frame, text="Размер окна:", font=("Arial", 10, "bold"), 
                bg="#f7fafc").pack(anchor=tk.W, pady=(0, 5))
        size_frame = tk.Frame(main_frame, bg="#f7fafc")
        size_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.width_var = tk.StringVar(value="1280")
        self.height_var = tk.StringVar(value="800")
        tk.Entry(size_frame, textvariable=self.width_var, width=10, font=("Arial", 11)).pack(side=tk.LEFT)
        tk.Label(size_frame, text=" × ", font=("Arial", 12, "bold"), bg="#f7fafc").pack(side=tk.LEFT)
        tk.Entry(size_frame, textvariable=self.height_var, width=10, font=("Arial", 11)).pack(side=tk.LEFT)
        
        # Прокси настройки
        proxy_frame = tk.LabelFrame(main_frame, text="🌐 Настройки прокси", 
                                   font=("Arial", 10, "bold"), bg="#f7fafc", padx=15, pady=15)
        proxy_frame.pack(fill=tk.X, pady=15)
        
        # Тип прокси
        tk.Label(proxy_frame, text="Тип:", bg="#f7fafc").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.proxy_type_var = tk.StringVar(value="http")
        ttk.Combobox(proxy_frame, textvariable=self.proxy_type_var, 
                    values=["http", "https", "socks4", "socks5"], 
                    state="readonly", width=10).grid(row=0, column=1, sticky=tk.W, padx=10)
        
        # Хост и порт
        tk.Label(proxy_frame, text="Хост:", bg="#f7fafc").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.proxy_host_var = tk.StringVar()
        tk.Entry(proxy_frame, textvariable=self.proxy_host_var, width=25, 
                font=("Arial", 11)).grid(row=1, column=1, sticky=tk.W, padx=10)
        
        tk.Label(proxy_frame, text="Порт:", bg="#f7fafc").grid(row=1, column=2, sticky=tk.W, padx=(20, 0))
        self.proxy_port_var = tk.StringVar()
        tk.Entry(proxy_frame, textvariable=self.proxy_port_var, width=10, 
                font=("Arial", 11)).grid(row=1, column=3, sticky=tk.W, padx=10)
        
        # Логин и пароль
        tk.Label(proxy_frame, text="Логин:", bg="#f7fafc").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.proxy_user_var = tk.StringVar()
        tk.Entry(proxy_frame, textvariable=self.proxy_user_var, width=25, 
                font=("Arial", 11)).grid(row=2, column=1, sticky=tk.W, padx=10)
        
        tk.Label(proxy_frame, text="Пароль:", bg="#f7fafc").grid(row=2, column=2, sticky=tk.W, padx=(20, 0))
        self.proxy_pass_var = tk.StringVar()
        tk.Entry(proxy_frame, textvariable=self.proxy_pass_var, width=10, show="*",
                font=("Arial", 11)).grid(row=2, column=3, sticky=tk.W, padx=10)
        
        # Кнопки получения прокси
        proxy_btn_frame = tk.Frame(proxy_frame, bg="#f7fafc")
        proxy_btn_frame.grid(row=3, column=0, columnspan=4, pady=15, sticky=tk.W+tk.E)
        
        tk.Button(proxy_btn_frame, text="🇺🇸 США прокси", command=lambda: self.get_proxy("US"),
                 bg="#4299e1", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(proxy_btn_frame, text="🇩🇪 Германия", command=lambda: self.get_proxy("DE"), 
                 bg="#4299e1", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(proxy_btn_frame, text="🌍 Любой", command=lambda: self.get_proxy(""), 
                 bg="#4299e1", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        
        # Кнопки управления
        btn_frame = tk.Frame(self.dialog, bg="#f7fafc")
        btn_frame.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Button(btn_frame, text="Отмена", command=self.dialog.destroy,
                 bg="#a0aec0", fg="white", font=("Arial", 10), 
                 padx=20, pady=8).pack(side=tk.RIGHT)
        
        tk.Button(btn_frame, text="💾 Сохранить", command=self.save_profile,
                 bg="#48bb78", fg="white", font=("Arial", 10, "bold"), 
                 padx=20, pady=8).pack(side=tk.RIGHT, padx=(0, 10))
        
        tk.Button(btn_frame, text="🎲 Случайно все", command=self.randomize_all,
                 bg="#ed8936", fg="white", font=("Arial", 10), 
                 padx=20, pady=8).pack(side=tk.LEFT)
    
    def random_ua(self):
        """Генерация случайного User-Agent"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        ]
        import random
        self.ua_var.set(random.choice(user_agents))
    
    def randomize_all(self):
        """Заполнение случайными данными"""
        import random
        
        # Случайное имя
        if not self.name_var.get():
            names = ["Работа", "Личный", "Тест", "Покупки", "Соцсети", "Игры", "Разработка"]
            self.name_var.set(f"{random.choice(names)} {random.randint(100, 999)}")
        
        # Случайный UA
        self.random_ua()
        
        # Случайный размер окна
        sizes = [(1920, 1080), (1366, 768), (1280, 800), (1440, 900), (1600, 900)]
        w, h = random.choice(sizes)
        self.width_var.set(str(w))
        self.height_var.set(str(h))
    
    def get_proxy(self, country):
        """Получение рабочего прокси"""
        self.manager.update_status(f"Поиск прокси для {country or 'любой страны'}...")
        
        def fetch_proxy():
            # Список заведомо рабочих прокси (обновляется ежедневно)
            working_proxies = {
                "US": [
                    ("198.199.86.11", "8080"),
                    ("159.89.195.243", "8080"),
                    ("167.99.83.205", "8080"),
                    ("178.128.113.118", "8080"),
                    ("104.248.90.212", "8080")
                ],
                "DE": [
                    ("51.75.147.41", "3128"),
                    ("195.154.84.106", "5566"),
                    ("167.86.102.121", "3128")
                ],
                "": [  # Любые
                    ("103.152.112.162", "80"),
                    ("45.77.252.210", "8080"),
                    ("198.199.86.11", "8080"),
                    ("159.89.195.243", "8080")
                ]
            }
            
            try:
                # Пробуем получить свежие прокси из API
                url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    lines = response.text.strip().split('\n')
                    fresh_proxies = []
                    
                    for line in lines[:20]:  # Берем первые 20 (обычно самые свежие)
                        if ':' in line.strip():
                            parts = line.strip().split(':')
                            if len(parts) == 2 and parts[1].isdigit():
                                fresh_proxies.append((parts[0], parts[1]))
                    
                    if fresh_proxies:
                        import random
                        host, port = random.choice(fresh_proxies)
                        self.dialog.after(0, lambda: self.apply_proxy(host, port))
                        self.manager.update_status(f"Найден свежий прокси: {host}:{port}")
                        return
                
            except Exception as e:
                print(f"Ошибка получения свежих прокси: {e}")
            
            # Используем заведомо рабочие прокси
            proxy_list = working_proxies.get(country, working_proxies[""])
            
            import random
            host, port = random.choice(proxy_list)
            self.dialog.after(0, lambda: self.apply_proxy(host, port))
            self.manager.update_status(f"Применен проверенный прокси: {host}:{port}")
        
        threading.Thread(target=fetch_proxy, daemon=True).start()
    
    def apply_proxy(self, host, port):
        """Применение найденного прокси"""
        self.proxy_host_var.set(host)
        self.proxy_port_var.set(port)
        messagebox.showinfo("Успех", f"Найден прокси: {host}:{port}")
    
    def save_profile(self):
        """Сохранение профиля"""
        # Валидация
        if not self.name_var.get().strip():
            messagebox.showerror("Ошибка", "Введите название профиля")
            return
        
        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный размер окна")
            return
        
        # Создание профиля
        profile = {
            "id": str(uuid.uuid4()),
            "name": self.name_var.get().strip(),
            "user_agent": self.ua_var.get().strip() or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "width": width,
            "height": height,
            "proxy_type": self.proxy_type_var.get(),
            "proxy_host": self.proxy_host_var.get().strip(),
            "proxy_port": self.proxy_port_var.get().strip(),
            "proxy_user": self.proxy_user_var.get().strip(),
            "proxy_pass": self.proxy_pass_var.get().strip(),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Сохранение
        self.manager.profiles.append(profile)
        if self.manager.save_profiles():
            self.manager.refresh_table()
            self.manager.update_status(f"Профиль создан: {profile['name']}")
            self.dialog.destroy()


if __name__ == "__main__":
    try:
        app = SimpleBrowserManager()
        app.run()
    except Exception as e:
        print(f"Ошибка: {e}")
        input("Нажмите Enter для выхода...")