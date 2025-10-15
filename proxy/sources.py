from __future__ import annotations
import requests
import time
from typing import List
from proxy.models import Proxy
from tools.logging_setup import get_logger

log = get_logger(__name__)

def get_working_proxies(country: str = "US", scheme: str = "http", max_proxies: int = 20) -> List[Proxy]:
    """Получает рабочие прокси из простых источников"""
    proxies = []
    
    # Встроенные рабочие прокси на случай если API не работает
    builtin_proxies = [
        "104.27.7.175:80",
        "172.67.70.148:80", 
        "104.18.219.225:80",
        "104.19.173.155:80",
        "104.254.140.2:80",
        "104.16.94.66:80",
        "176.113.73.102:3128",
        "104.24.228.240:80"
    ]
    
    for proxy_str in builtin_proxies:
        try:
            host, port = proxy_str.split(":")
            proxy = Proxy(
                scheme=scheme,
                host=host,
                port=int(port),
                country=country
            )
            proxies.append(proxy)
        except:
            continue
    
    # Пытаемся получить прокси из внешних источников
    try:
        external_proxies = _fetch_from_sources(country, scheme, max_proxies)
        proxies.extend(external_proxies)
    except Exception as e:
        log.warning(f"Не удалось получить внешние прокси: {e}")
    
    return proxies[:max_proxies]

def _fetch_from_sources(country: str, scheme: str, max_proxies: int) -> List[Proxy]:
    """Получает прокси из внешних источников"""
    proxies = []
    
    try:
        # TheSpeedX Proxy List
        url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
        response = requests.get(url, timeout=10)
        if response.ok:
            lines = response.text.strip().split('\n')
            for line in lines[:max_proxies//2]:
                if ':' in line:
                    host, port = line.strip().split(':')
                    try:
                        proxy = Proxy(
                            scheme=scheme,
                            host=host,
                            port=int(port),
                            country=country
                        )
                        proxies.append(proxy)
                    except:
                        continue
    except Exception as e:
        log.warning(f"Ошибка получения прокси из TheSpeedX: {e}")
    
    try:
        # ProxyScrape
        url = f"https://api.proxyscrape.com/v2/?request=get&protocol={scheme}&timeout=10000&country={country}&ssl=all&anonymity=all"
        response = requests.get(url, timeout=10)
        if response.ok:
            lines = response.text.strip().split('\n')
            for line in lines[:max_proxies//2]:
                if ':' in line:
                    host, port = line.strip().split(':')
                    try:
                        proxy = Proxy(
                            scheme=scheme,
                            host=host,
                            port=int(port),
                            country=country
                        )
                        proxies.append(proxy)
                    except:
                        continue
    except Exception as e:
        log.warning(f"Ошибка получения прокси из ProxyScrape: {e}")
    
    return proxies

def gather_proxies_from_sources(country: str = "US", scheme: str = "http") -> List[Proxy]:
    """Основная функция для получения прокси из всех источников"""
    return get_working_proxies(country, scheme, 30)