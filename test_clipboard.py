import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Тест Ctrl+C/V")
root.geometry("400x200")

label = tk.Label(root, text="Попробуй скопировать и вставить текст с помощью Ctrl+C и Ctrl+V:")
label.pack(pady=10)

entry1 = ttk.Entry(root, width=50)
entry1.pack(pady=5)
entry1.insert(0, "Скопируй этот текст (Ctrl+C)")

entry2 = ttk.Entry(root, width=50)
entry2.pack(pady=5)

status_label = tk.Label(root, text="Статус: ожидание", fg="blue")
status_label.pack(pady=10)

def on_key(event):
    status_label.config(text=f"Нажата клавиша: {event.keysym} (state={event.state})")

root.bind("<Key>", on_key)

root.mainloop()
