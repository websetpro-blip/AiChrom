# nixtio_theme.py - Современная тема в стиле Nixtio/Passion Finder
import tkinter as tk
from tkinter import ttk
import math

# === ЦВЕТОВАЯ СХЕМА В СТИЛЕ NIXTIO ===
COLORS = {
    # Основные цвета
    "primary": "#667eea",           # Синий градиент
    "primary_dark": "#5a67d8",     # Темно-синий
    "secondary": "#764ba2",         # Фиолетовый градиент
    "secondary_dark": "#6b46c1",   # Темно-фиолетовый
    
    # Фоны
    "background": "#f8f9fa",        # Светлый фон
    "surface": "#ffffff",           # Белые карточки
    "surface_hover": "#f1f5f9",    # Hover состояние
    "surface_elevated": "#ffffff",  # Приподнятые элементы
    
    # Текст
    "text": "#2d3748",             # Темный текст
    "text_light": "#718096",       # Серый текст
    "text_muted": "#a0aec0",       # Приглушенный текст
    "text_white": "#ffffff",       # Белый текст
    
    # Статусы
    "success": "#48bb78",          # Зеленый
    "success_light": "#c6f6d5",   # Светло-зеленый
    "warning": "#ed8936",          # Оранжевый
    "warning_light": "#fbd38d",   # Светло-оранжевый
    "error": "#f56565",            # Красный
    "error_light": "#fed7d7",     # Светло-красный
    "info": "#4299e1",             # Синий
    "info_light": "#bee3f8",      # Светло-синий
    
    # Границы и разделители
    "border": "#e2e8f0",           # Светлые границы
    "border_light": "#f1f5f9",    # Очень светлые границы
    "divider": "#cbd5e0",         # Разделители
    
    # Тени
    "shadow_light": "rgba(0,0,0,0.1)",
    "shadow_medium": "rgba(0,0,0,0.15)",
    "shadow_heavy": "rgba(0,0,0,0.25)",
}

# === ШРИФТЫ ===
FONTS = {
    "heading": ("Inter", 24, "bold"),
    "subheading": ("Inter", 18, "bold"),
    "body": ("Inter", 12, "normal"),
    "body_bold": ("Inter", 12, "bold"),
    "caption": ("Inter", 10, "normal"),
    "button": ("Inter", 11, "bold"),
    "small": ("Inter", 9, "normal"),
}

class NixtioTheme:
    """Класс для создания UI компонентов в стиле Nixtio"""
    
    @staticmethod
    def create_gradient_canvas(parent, width, height, color1, color2, direction="horizontal"):
        """Создание Canvas с градиентным фоном"""
        canvas = tk.Canvas(parent, width=width, height=height, highlightthickness=0)
        
        # Создаем градиент
        if direction == "horizontal":
            for i in range(width):
                ratio = i / width
                r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
                r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
                
                r = int(r1 + (r2 - r1) * ratio)
                g = int(g1 + (g2 - g1) * ratio)
                b = int(b1 + (b2 - b1) * ratio)
                
                color = f"#{r:02x}{g:02x}{b:02x}"
                canvas.create_line(i, 0, i, height, fill=color, width=1)
        else:  # vertical
            for i in range(height):
                ratio = i / height
                r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
                r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
                
                r = int(r1 + (r2 - r1) * ratio)
                g = int(g1 + (g2 - g1) * ratio)
                b = int(b1 + (b2 - b1) * ratio)
                
                color = f"#{r:02x}{g:02x}{b:02x}"
                canvas.create_line(0, i, width, i, fill=color, width=1)
        
        return canvas
    
    @staticmethod
    def create_glass_card(parent, width=None, height=None, **kwargs):
        """Создание стеклянной карточки с эффектом размытия"""
        card = tk.Frame(parent, 
                       bg=COLORS["surface"],
                       relief="flat",
                       bd=0,
                       **kwargs)
        
        if width:
            card.configure(width=width)
        if height:
            card.configure(height=height)
            
        # Добавляем тень через Canvas
        shadow_canvas = tk.Canvas(card, height=2, highlightthickness=0, bg=COLORS["background"])
        shadow_canvas.pack(fill=tk.X, side=tk.BOTTOM)
        shadow_canvas.create_line(0, 1, 1000, 1, fill=COLORS["border"], width=1)
        
        return card
    
    @staticmethod
    def create_modern_button(parent, text, command=None, style="primary", width=None, height=40):
        """Создание современной кнопки с градиентом"""
        if style == "primary":
            bg_color = COLORS["primary"]
            fg_color = COLORS["text_white"]
            hover_color = COLORS["primary_dark"]
        elif style == "secondary":
            bg_color = COLORS["secondary"]
            fg_color = COLORS["text_white"]
            hover_color = COLORS["secondary_dark"]
        elif style == "success":
            bg_color = COLORS["success"]
            fg_color = COLORS["text_white"]
            hover_color = "#38a169"
        elif style == "warning":
            bg_color = COLORS["warning"]
            fg_color = COLORS["text_white"]
            hover_color = "#dd6b20"
        elif style == "danger":
            bg_color = COLORS["error"]
            fg_color = COLORS["text_white"]
            hover_color = "#e53e3e"
        else:  # outline
            bg_color = COLORS["surface"]
            fg_color = COLORS["text"]
            hover_color = COLORS["surface_hover"]
        
        # Создаем кнопку
        btn = tk.Button(parent,
                       text=text,
                       command=command,
                       bg=bg_color,
                       fg=fg_color,
                       font=FONTS["button"],
                       relief="flat",
                       bd=0,
                       padx=20,
                       pady=10,
                       cursor="hand2")
        
        if width:
            btn.configure(width=width)
        if height:
            btn.configure(height=height//4)  # tkinter использует строки
        
        # Hover эффекты
        def on_enter(e):
            btn.configure(bg=hover_color)
        
        def on_leave(e):
            btn.configure(bg=bg_color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn
    
    @staticmethod
    def create_status_badge(parent, text, status="info"):
        """Создание статусного бейджа"""
        if status == "success":
            bg_color = COLORS["success_light"]
            fg_color = COLORS["success"]
        elif status == "warning":
            bg_color = COLORS["warning_light"]
            fg_color = COLORS["warning"]
        elif status == "error":
            bg_color = COLORS["error_light"]
            fg_color = COLORS["error"]
        else:  # info
            bg_color = COLORS["info_light"]
            fg_color = COLORS["info"]
        
        badge = tk.Label(parent,
                        text=text,
                        bg=bg_color,
                        fg=fg_color,
                        font=FONTS["caption"],
                        padx=8,
                        pady=2,
                        relief="flat",
                        bd=0)
        
        return badge
    
    @staticmethod
    def create_modern_entry(parent, placeholder="", width=None):
        """Создание современного поля ввода"""
        entry_frame = tk.Frame(parent, bg=COLORS["surface"], relief="flat", bd=1)
        
        entry = tk.Entry(entry_frame,
                        font=FONTS["body"],
                        relief="flat",
                        bd=0,
                        bg=COLORS["surface"],
                        fg=COLORS["text"],
                        insertbackground=COLORS["text"])
        
        if width:
            entry.configure(width=width)
        
        entry.pack(fill=tk.X, padx=12, pady=8)
        
        # Placeholder эффект
        if placeholder:
            entry.insert(0, placeholder)
            entry.configure(fg=COLORS["text_muted"])
            
            def on_focus_in(e):
                if entry.get() == placeholder:
                    entry.delete(0, tk.END)
                    entry.configure(fg=COLORS["text"])
            
            def on_focus_out(e):
                if not entry.get():
                    entry.insert(0, placeholder)
                    entry.configure(fg=COLORS["text_muted"])
            
            entry.bind("<FocusIn>", on_focus_in)
            entry.bind("<FocusOut>", on_focus_out)
        
        return entry_frame, entry
    
    @staticmethod
    def create_modern_table(parent, columns, data=None):
        """Создание современной таблицы"""
        # Создаем фрейм для таблицы
        table_frame = tk.Frame(parent, bg=COLORS["surface"], relief="flat", bd=1)
        
        # Создаем Treeview
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        
        # Настраиваем стиль
        style = ttk.Style()
        style.theme_use("clam")
        
        # Конфигурируем стили
        style.configure("Treeview",
                       background=COLORS["surface"],
                       foreground=COLORS["text"],
                       fieldbackground=COLORS["surface"],
                       borderwidth=0,
                       font=FONTS["body"])
        
        style.configure("Treeview.Heading",
                       background=COLORS["background"],
                       foreground=COLORS["text"],
                       font=FONTS["body_bold"],
                       borderwidth=0)
        
        style.map("Treeview",
                 background=[("selected", COLORS["primary"])],
                 foreground=[("selected", COLORS["text_white"])])
        
        # Настраиваем колонки
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="w")
        
        # Добавляем скроллбар
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Размещаем элементы
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        return table_frame, tree
    
    @staticmethod
    def apply_theme_to_root(root):
        """Применение темы к главному окну"""
        root.configure(bg=COLORS["background"])
        
        # Настраиваем стили для ttk
        style = ttk.Style()
        style.theme_use("clam")
        
        # Общие стили
        style.configure("TLabel",
                       background=COLORS["background"],
                       foreground=COLORS["text"],
                       font=FONTS["body"])
        
        style.configure("TFrame",
                       background=COLORS["background"])
        
        style.configure("TButton",
                       background=COLORS["primary"],
                       foreground=COLORS["text_white"],
                       font=FONTS["button"],
                       relief="flat",
                       borderwidth=0)
        
        style.map("TButton",
                 background=[("active", COLORS["primary_dark"])])
        
        return style

# === УТИЛИТЫ ===
def hex_to_rgb(hex_color):
    """Конвертация HEX в RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    """Конвертация RGB в HEX"""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

def interpolate_color(color1, color2, ratio):
    """Интерполяция между двумя цветами"""
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    
    r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * ratio)
    g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * ratio)
    b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * ratio)
    
    return rgb_to_hex((r, g, b))
