import tkinter as tk
from tkinter import ttk

def attach_clipboard_handlers(widget):
    """Test clipboard handlers"""
    def do_copy(w):
        try:
            if w.selection_present():
                text = w.selection_get()
                w.clipboard_clear()
                w.clipboard_append(text)
                print(f"Copied: {text}")
        except tk.TclError as e:
            print(f"Copy error: {e}")
    
    def do_paste(w):
        try:
            text = w.clipboard_get()
            if w.selection_present():
                w.delete(tk.SEL_FIRST, tk.SEL_LAST)
            w.insert(tk.INSERT, text)
            print(f"Pasted: {text}")
        except tk.TclError as e:
            print(f"Paste error: {e}")
    
    widget.bind("<Control-c>", lambda e: do_copy(e.widget) or "break")
    widget.bind("<Control-C>", lambda e: do_copy(e.widget) or "break")
    widget.bind("<Control-v>", lambda e: do_paste(e.widget) or "break")
    widget.bind("<Control-V>", lambda e: do_paste(e.widget) or "break")
    print(f"Handlers attached to {widget}")

root = tk.Tk()
root.title("Test Ctrl+C/V")
root.geometry("500x300")

tk.Label(root, text="Поле 1: Скопируй этот текст (выдели и нажми Ctrl+C)", font=("Arial", 10)).pack(pady=5)
entry1 = ttk.Entry(root, width=50)
entry1.pack(pady=5)
entry1.insert(0, "186.65.113.39")
attach_clipboard_handlers(entry1)

tk.Label(root, text="Поле 2: Вставь сюда (нажми Ctrl+V)", font=("Arial", 10)).pack(pady=5)
entry2 = ttk.Entry(root, width=50)
entry2.pack(pady=5)
attach_clipboard_handlers(entry2)

tk.Label(root, text="Поле 3: Для проверки", font=("Arial", 10)).pack(pady=5)
entry3 = ttk.Entry(root, width=50)
entry3.pack(pady=5)
attach_clipboard_handlers(entry3)

status = tk.Label(root, text="Статус: готов к тесту", fg="blue")
status.pack(pady=20)

def update_status(msg):
    status.config(text=msg)

root.bind("<Key>", lambda e: update_status(f"Клавиша: {e.keysym}, state={e.state}, char={repr(e.char)}"))

print("=== Тест запущен ===")
print("1. Выдели текст в первом поле")
print("2. Нажми Ctrl+C")
print("3. Кликни во второе поле")
print("4. Нажми Ctrl+V")

root.mainloop()
