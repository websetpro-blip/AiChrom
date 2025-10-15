#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Простой скрипт для получения и проверки рабочих прокси
БЕЗ СЛОЖНОСТЕЙ - ПРОСТО РАБОТАЕТ!
"""

import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_proxy(proxy_line):
    """Проверяет один прокси на работоспособность"""
    try:
        if ':' not in proxy_line:
            return None
        
        host, port = proxy_line.strip().split(':', 1)
        
        # Проверяем HTTP прокси
        proxy_dict = {
            "http": f"http://{host}:{port}",
            "https": f"http://{host}:{port}"
        }
        
        # Быстрая проверка через ipify
        response = requests.get("https://api.ipify.org?format=json", 
                              proxies=proxy_dict, timeout=5)
        
        if response.status_code == 200:
            ip_data = response.json()
            real_ip = ip_data.get("ip")
            
            if real_ip:
                # Получаем страну
                try:
                    geo_response = requests.get(f"http://ip-api.com/json/{real_ip}", 
                                              timeout=3)
                    if geo_response.status_code == 200:
                        geo_data = geo_response.json()
                        country = geo_data.get("countryCode", "XX")
                        return f"{host}:{port} -> {real_ip} ({country})"
                except:
                    pass
                
                return f"{host}:{port} -> {real_ip}"
    
    except Exception:
        pass
    
    return None

def get_fresh_proxies():
    """Получает свежие прокси из надежных источников"""
    print("🔍 Поиск свежих прокси...")
    
    sources = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "https://api.proxyscrape.com/v2/?request=get&format=textplain&protocol=http&timeout=5000&country=all",
    ]
    
    all_proxies = []
    
    for source in sources:
        try:
            print(f"📡 Загружаю из: {source}")
            response = requests.get(source, timeout=15)
            
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                valid_lines = [line.strip() for line in lines 
                             if ':' in line and not line.startswith('#')]
                all_proxies.extend(valid_lines[:100])  # Берем по 100 из каждого источника
                print(f"✅ Получено {len(valid_lines)} прокси")
            else:
                print(f"❌ Ошибка {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка источника: {e}")
    
    # Убираем дубликаты
    unique_proxies = list(set(all_proxies))
    print(f"📋 Всего уникальных прокси: {len(unique_proxies)}")
    
    return unique_proxies

def validate_proxies(proxy_list, max_workers=50, limit=30):
    """Проверяет прокси на работоспособность"""
    print(f"🧪 Тестирование {len(proxy_list)} прокси (максимум {limit} рабочих)...")
    
    working_proxies = []
    tested_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Запускаем тесты
        futures = {executor.submit(test_proxy, proxy): proxy for proxy in proxy_list}
        
        for future in as_completed(futures):
            tested_count += 1
            result = future.result()
            
            if result:
                working_proxies.append(result)
                print(f"✅ {result}")
                
                # Ограничиваем количество
                if len(working_proxies) >= limit:
                    print(f"🎯 Найдено {limit} рабочих прокси, останавливаем поиск")
                    break
            
            # Показываем прогресс
            if tested_count % 20 == 0:
                print(f"🔄 Протестировано: {tested_count}, найдено рабочих: {len(working_proxies)}")
    
    return working_proxies

def save_working_proxies(working_proxies):
    """Сохраняет рабочие прокси в файл"""
    if working_proxies:
        with open("working_proxies.txt", "w", encoding="utf-8") as f:
            for proxy in working_proxies:
                f.write(proxy + "\n")
        
        print(f"💾 Сохранено {len(working_proxies)} рабочих прокси в working_proxies.txt")
        return True
    
    return False

def main():
    """Главная функция"""
    print("🌐 Простой сборщик рабочих прокси")
    print("=" * 50)
    
    # Получаем свежие прокси
    proxy_list = get_fresh_proxies()
    
    if not proxy_list:
        print("❌ Не удалось получить прокси из источников")
        return
    
    # Тестируем прокси
    working_proxies = validate_proxies(proxy_list, max_workers=50, limit=30)
    
    if working_proxies:
        print(f"\n🎉 Найдено {len(working_proxies)} рабочих прокси!")
        
        # Показываем результаты
        print("\n📋 Рабочие прокси:")
        for proxy in working_proxies:
            print(f"  {proxy}")
        
        # Сохраняем в файл
        save_working_proxies(working_proxies)
        
        print("\n✅ Готово! Используйте прокси из файла working_proxies.txt")
    else:
        print("❌ Не найдено рабочих прокси")

if __name__ == "__main__":
    main()