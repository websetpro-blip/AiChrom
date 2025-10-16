#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Geonode Proxy Fetcher
Рабочий скрипт для получения прокси с Geonode.com
"""

import requests
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_geonode_proxies(country="", limit=50):
    """Получает прокси с Geonode API"""
    try:
        # API URL для получения прокси
        api_url = 'https://proxylist.geonode.com/api/proxy-list'
        params = {
            'limit': limit,
            'page': 1,
            'sort_by': 'lastChecked',
            'sort_type': 'desc',
            'protocols': 'http,https'
        }
        
        if country:
            params['country'] = country.upper()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(api_url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            proxies = data.get('data', [])
            
            # Конвертируем в нужный формат
            result = []
            for proxy in proxies:
                ip = proxy.get('ip')
                port = proxy.get('port')
                country_code = proxy.get('country', '').upper()
                protocols = proxy.get('protocols', ['http'])
                
                if ip and port:
                    for protocol in protocols:
                        result.append((f"{ip}:{port}", protocol.upper(), country_code))
            
            return result
        else:
            print(f"Ошибка API: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Ошибка получения прокси: {e}")
        return []

def test_proxy(proxy_tuple):
    """Тестирует один прокси"""
    addr, protocol, country = proxy_tuple
    
    try:
        # Быстрая проверка через ipify.org
        test_url = 'https://api.ipify.org?format=json'
        proxy_dict = {protocol.lower(): f'{protocol.lower()}://{addr}'}
        
        response = requests.get(test_url, proxies=proxy_dict, timeout=5)
        
        if response.status_code == 200:
            result_ip = response.json().get('ip')
            return (addr, protocol, country, result_ip)
        else:
            return None
            
    except Exception:
        return None

def get_candidates(country=None, types=None, limit=50):
    """Новый API для совместимости с proxy_pool.py"""
    if not types:
        types = ["HTTP", "HTTPS"]
    
    # Получаем прокси
    all_proxies = fetch_geonode_proxies(country or "", limit * 2)
    
    # Фильтруем по типам
    filtered = []
    for addr, protocol, country_code in all_proxies:
        if protocol.upper() in [t.upper() for t in types]:
            filtered.append({
                "addr": addr,
                "proto": protocol.upper(),
                "cc": country_code
            })
    
    return filtered[:limit]

def get_working_proxies(country="", limit=20, test_limit=50):
    """Получает рабочие прокси с Geonode"""
    print(f"🔍 Получаю прокси с Geonode для страны: {country or 'любой'}")
    
    # Получаем прокси
    all_proxies = fetch_geonode_proxies(country, test_limit)
    print(f"📡 Получено {len(all_proxies)} прокси")
    
    if not all_proxies:
        return []
    
    # Тестируем прокси параллельно
    working_proxies = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(test_proxy, proxy) for proxy in all_proxies]
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                addr, protocol, country, real_ip = result
                working_proxies.append((addr, protocol, country))
                print(f"✅ {addr} ({country}) -> {real_ip}")
                
                if len(working_proxies) >= limit:
                    break
    
    print(f"🎯 Найдено {len(working_proxies)} рабочих прокси")
    return working_proxies

if __name__ == "__main__":
    # Тестируем скрипт
    print("=== Тест Geonode Proxy Fetcher ===")
    
    # Тест 1: Прокси для США
    us_proxies = get_working_proxies("US", limit=5, test_limit=20)
    print(f"\n🇺🇸 Прокси для США: {len(us_proxies)}")
    for proxy in us_proxies:
        print(f"  {proxy[0]} ({proxy[2]})")
    
    # Тест 2: Любые прокси
    any_proxies = get_working_proxies("", limit=5, test_limit=20)
    print(f"\n🌍 Любые прокси: {len(any_proxies)}")
    for proxy in any_proxies:
        print(f"  {proxy[0]} ({proxy[2]})")
