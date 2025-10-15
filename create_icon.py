"""
Создание иконки для AiChrome
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_aichrome_icon():
    # Создаем изображение 256x256 для иконки
    size = 256
    img = Image.new('RGB', (size, size), color='#2563eb')  # Синий фон
    draw = ImageDraw.Draw(img)
    
    # Рисуем круглый фон
    margin = 20
    draw.ellipse([margin, margin, size-margin, size-margin], fill='#1e40af', outline='#60a5fa', width=8)
    
    # Рисуем стилизованную букву "A" и "C"
    try:
        # Пытаемся использовать системный шрифт
        font = ImageFont.truetype("arial.ttf", 120)
    except:
        # Если не найден, используем дефолтный
        font = ImageFont.load_default()
    
    # Рисуем текст "AC" (AiChrome)
    text = "AC"
    # Получаем размер текста для центрирования
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    text_x = (size - text_width) // 2
    text_y = (size - text_height) // 2 - 10
    
    # Тень для текста
    draw.text((text_x + 4, text_y + 4), text, font=font, fill='#000000')
    # Основной текст
    draw.text((text_x, text_y), text, font=font, fill='#ffffff')
    
    # Рисуем маленький chrome-подобный акцент (круг в правом нижнем углу)
    accent_size = 60
    accent_pos = size - accent_size - 30
    draw.ellipse([accent_pos, accent_pos, accent_pos + accent_size, accent_pos + accent_size], 
                 fill='#10b981', outline='#34d399', width=3)
    
    # Сохраняем в разных размерах для .ico
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []
    for ico_size in icon_sizes:
        resized = img.resize(ico_size, Image.Resampling.LANCZOS)
        images.append(resized)
    
    # Сохраняем как .ico файл
    icon_path = os.path.join(os.path.dirname(__file__), "aichrome.ico")
    images[0].save(icon_path, format='ICO', sizes=icon_sizes)
    
    # Также сохраняем PNG для предварительного просмотра
    png_path = os.path.join(os.path.dirname(__file__), "aichrome.png")
    img.save(png_path)
    
    print(f"Иконка создана:")
    print(f"  - {icon_path}")
    print(f"  - {png_path}")
    return icon_path

if __name__ == "__main__":
    create_aichrome_icon()
