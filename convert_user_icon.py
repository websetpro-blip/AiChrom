"""
Конвертация пользовательской PNG иконки в ICO формат
"""
from PIL import Image
import os

def convert_png_to_ico():
    source_path = r"C:\AI\AiChrome\19_diamond_holo_circui.png"
    output_ico = r"C:\AI\AiChrome\aichrome.ico"
    output_png = r"C:\AI\AiChrome\aichrome.png"
    
    if not os.path.exists(source_path):
        print(f"Ошибка: файл не найден: {source_path}")
        return
    
    # Открываем исходную картинку
    img = Image.open(source_path)
    
    # Конвертируем в RGB если нужно
    if img.mode in ('RGBA', 'LA'):
        # Создаем белый фон для прозрачных областей
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[3])  # Используем альфа-канал как маску
        else:
            background.paste(img, mask=img.split()[1])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Сохраняем PNG версию
    img.save(output_png)
    print(f"[OK] PNG sohranyen: {output_png}")
    
    # Создаем иконки разных размеров
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []
    
    for ico_size in icon_sizes:
        resized = img.resize(ico_size, Image.Resampling.LANCZOS)
        images.append(resized)
    
    # Сохраняем как ICO
    images[0].save(output_ico, format='ICO', sizes=icon_sizes)
    print(f"[OK] ICO sohranyen: {output_ico}")
    print(f"\nIkonka uspeshno konvertirovana!")

if __name__ == "__main__":
    convert_png_to_ico()
