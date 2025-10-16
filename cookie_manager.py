import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import shutil

class CookieManager:
    """
    Менеджер для управления cookies профилей Chrome через SQLite-файл Cookies.
    Поддерживает чтение, добавление, удаление, импорт и экспорт cookies.
    """
    
    def __init__(self, profile_path: str):
        """
        Инициализация менеджера cookies.
        
        Args:
            profile_path: Путь к директории профиля Chrome
        """
        self.profile_path = profile_path
        self.cookies_db_path = os.path.join(profile_path, 'Cookies')
        
    def _connect_db(self) -> sqlite3.Connection:
        """
        Создание подключения к базе данных cookies.
        
        Returns:
            Объект подключения к SQLite
        """
        if not os.path.exists(self.cookies_db_path):
            raise FileNotFoundError(f"Файл Cookies не найден: {self.cookies_db_path}")
        
        # Создаем временную копию для безопасной работы
        temp_db = self.cookies_db_path + '.temp'
        shutil.copy2(self.cookies_db_path, temp_db)
        
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _commit_changes(self, temp_conn: sqlite3.Connection):
        """
        Сохранение изменений из временной БД в основную.
        
        Args:
            temp_conn: Временное подключение к БД
        """
        temp_db = self.cookies_db_path + '.temp'
        temp_conn.close()
        
        # Заменяем оригинальный файл
        if os.path.exists(self.cookies_db_path):
            os.remove(self.cookies_db_path)
        shutil.move(temp_db, self.cookies_db_path)
    
    def read_cookies(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Чтение cookies из базы данных.
        
        Args:
            domain: Фильтр по домену (опционально)
            
        Returns:
            Список словарей с данными cookies
        """
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            
            if domain:
                query = "SELECT * FROM cookies WHERE host_key LIKE ?"
                cursor.execute(query, (f'%{domain}%',))
            else:
                query = "SELECT * FROM cookies"
                cursor.execute(query)
            
            cookies = []
            for row in cursor.fetchall():
                cookie = {
                    'host_key': row['host_key'],
                    'name': row['name'],
                    'value': row['value'],
                    'path': row['path'],
                    'expires_utc': row['expires_utc'],
                    'is_secure': bool(row['is_secure']),
                    'is_httponly': bool(row['is_httponly']),
                    'has_expires': bool(row['has_expires']),
                    'is_persistent': bool(row['is_persistent']),
                    'priority': row['priority'],
                    'samesite': row['samesite'],
                }
                cookies.append(cookie)
            
            conn.close()
            # Удаляем временный файл
            os.remove(self.cookies_db_path + '.temp')
            return cookies
            
        except Exception as e:
            print(f"Ошибка чтения cookies: {e}")
            if os.path.exists(self.cookies_db_path + '.temp'):
                os.remove(self.cookies_db_path + '.temp')
            return []
    
    def add_cookie(self, cookie: Dict[str, Any]) -> bool:
        """
        Добавление нового cookie в базу данных.
        
        Args:
            cookie: Словарь с данными cookie
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            
            # Подготовка данных
            creation_utc = int(datetime.now().timestamp() * 1000000)
            last_access_utc = creation_utc
            expires_utc = cookie.get('expires_utc', 0)
            
            query = """
                INSERT INTO cookies (
                    creation_utc, host_key, name, value, path, expires_utc,
                    is_secure, is_httponly, last_access_utc, has_expires,
                    is_persistent, priority, samesite
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            cursor.execute(query, (
                creation_utc,
                cookie.get('host_key', ''),
                cookie.get('name', ''),
                cookie.get('value', ''),
                cookie.get('path', '/'),
                expires_utc,
                int(cookie.get('is_secure', False)),
                int(cookie.get('is_httponly', False)),
                last_access_utc,
                int(cookie.get('has_expires', True)),
                int(cookie.get('is_persistent', True)),
                cookie.get('priority', 1),
                cookie.get('samesite', -1)
            ))
            
            conn.commit()
            self._commit_changes(conn)
            return True
            
        except Exception as e:
            print(f"Ошибка добавления cookie: {e}")
            if os.path.exists(self.cookies_db_path + '.temp'):
                os.remove(self.cookies_db_path + '.temp')
            return False
    
    def delete_cookie(self, host_key: str, name: str, path: str = '/') -> bool:
        """
        Удаление cookie из базы данных.
        
        Args:
            host_key: Домен cookie
            name: Имя cookie
            path: Путь cookie (по умолчанию '/')
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            
            query = "DELETE FROM cookies WHERE host_key = ? AND name = ? AND path = ?"
            cursor.execute(query, (host_key, name, path))
            
            conn.commit()
            self._commit_changes(conn)
            return True
            
        except Exception as e:
            print(f"Ошибка удаления cookie: {e}")
            if os.path.exists(self.cookies_db_path + '.temp'):
                os.remove(self.cookies_db_path + '.temp')
            return False
    
    def delete_all_cookies(self, domain: Optional[str] = None) -> bool:
        """
        Удаление всех cookies или всех cookies для определенного домена.
        
        Args:
            domain: Домен для фильтрации (опционально)
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            
            if domain:
                query = "DELETE FROM cookies WHERE host_key LIKE ?"
                cursor.execute(query, (f'%{domain}%',))
            else:
                query = "DELETE FROM cookies"
                cursor.execute(query)
            
            conn.commit()
            self._commit_changes(conn)
            return True
            
        except Exception as e:
            print(f"Ошибка удаления cookies: {e}")
            if os.path.exists(self.cookies_db_path + '.temp'):
                os.remove(self.cookies_db_path + '.temp')
            return False
    
    def export_cookies(self, export_path: str, domain: Optional[str] = None) -> bool:
        """
        Экспорт cookies в JSON файл.
        
        Args:
            export_path: Путь для сохранения JSON файла
            domain: Фильтр по домену (опционально)
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            cookies = self.read_cookies(domain)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Ошибка экспорта cookies: {e}")
            return False
    
    def import_cookies(self, import_path: str, replace: bool = False) -> bool:
        """
        Импорт cookies из JSON файла.
        
        Args:
            import_path: Путь к JSON файлу с cookies
            replace: Если True, удалить существующие cookies перед импортом
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            if replace:
                self.delete_all_cookies()
            
            success_count = 0
            for cookie in cookies:
                if self.add_cookie(cookie):
                    success_count += 1
            
            print(f"Импортировано {success_count} из {len(cookies)} cookies")
            return success_count > 0
            
        except Exception as e:
            print(f"Ошибка импорта cookies: {e}")
            return False
    
    def update_cookie(self, host_key: str, name: str, new_value: str, path: str = '/') -> bool:
        """
        Обновление значения существующего cookie.
        
        Args:
            host_key: Домен cookie
            name: Имя cookie
            new_value: Новое значение
            path: Путь cookie (по умолчанию '/')
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            
            query = """
                UPDATE cookies 
                SET value = ?, last_access_utc = ?
                WHERE host_key = ? AND name = ? AND path = ?
            """
            
            last_access_utc = int(datetime.now().timestamp() * 1000000)
            cursor.execute(query, (new_value, last_access_utc, host_key, name, path))
            
            conn.commit()
            self._commit_changes(conn)
            return True
            
        except Exception as e:
            print(f"Ошибка обновления cookie: {e}")
            if os.path.exists(self.cookies_db_path + '.temp'):
                os.remove(self.cookies_db_path + '.temp')
            return False
    
    def get_cookie_count(self, domain: Optional[str] = None) -> int:
        """
        Получение количества cookies.
        
        Args:
            domain: Фильтр по домену (опционально)
            
        Returns:
            Количество cookies
        """
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            
            if domain:
                query = "SELECT COUNT(*) FROM cookies WHERE host_key LIKE ?"
                cursor.execute(query, (f'%{domain}%',))
            else:
                query = "SELECT COUNT(*) FROM cookies"
                cursor.execute(query)
            
            count = cursor.fetchone()[0]
            conn.close()
            
            # Удаляем временный файл
            if os.path.exists(self.cookies_db_path + '.temp'):
                os.remove(self.cookies_db_path + '.temp')
            
            return count
            
        except Exception as e:
            print(f"Ошибка получения количества cookies: {e}")
            if os.path.exists(self.cookies_db_path + '.temp'):
                os.remove(self.cookies_db_path + '.temp')
            return 0
