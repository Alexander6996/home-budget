import os
import sqlite3
from datetime import datetime

import pytz

from auth_utils import hash_password


def get_db_connection():
    """Подключение к базе данных"""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, 'budget.db')
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_moscow_time():
    """Получение текущего московского времени"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

def utility_processor():
    """Добавляем функции в контекст всех шаблонов"""
    return dict(get_moscow_time=get_moscow_time)

def init_db():
    """Инициализация базы данных"""
    print("🔄 Запуск процесса инициализации базы данных...")

    with get_db_connection() as conn:
        # Создаем таблицу пользователей
        conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Создаем таблицу категорий
        conn.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
            icon TEXT,
            color TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Создаем таблицу транзакций
        conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
            amount REAL NOT NULL,
            category_id INTEGER,
            description TEXT,
            date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Создаем таблицу лимитов расходов (ОБНОВЛЕННАЯ - добавлено поле period)
        conn.execute('''
        CREATE TABLE IF NOT EXISTS limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            amount_limit REAL NOT NULL,
            period TEXT DEFAULT 'monthly',
            month_year TEXT NOT NULL,
            user_id INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Создаем таблицу общего бюджета на месяц
        conn.execute('''
        CREATE TABLE IF NOT EXISTS monthly_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month_year TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, month_year),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Создаем таблицу целей накопления
        conn.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL DEFAULT 0,
            deadline DATE,
            auto_save_amount REAL DEFAULT 0,
            auto_save_frequency TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Создаем таблицу ежемесячных платежей
        conn.execute('''
        CREATE TABLE IF NOT EXISTS monthly_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            category_id INTEGER NOT NULL,
            payment_day INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(category_id) REFERENCES categories(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        ''')

        conn.execute('''
        CREATE TABLE IF NOT EXISTS monthly_payment_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            month_year TEXT NOT NULL,
            paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(payment_id, month_year),
            FOREIGN KEY(payment_id) REFERENCES monthly_payments(id)
        )
        ''')

        # Создаем таблицу коммунальных услуг (user_id может быть NULL)
        conn.execute('''
        CREATE TABLE IF NOT EXISTS utility_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utility_name TEXT NOT NULL,
            rate_per_unit REAL NOT NULL,
            unit TEXT NOT NULL,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Создаем таблицу показаний счетчиков (ДОБАВЛЯЕМ user_id)
        conn.execute('''
        CREATE TABLE IF NOT EXISTS utility_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utility_id INTEGER NOT NULL,
            reading REAL NOT NULL,
            reading_date DATE NOT NULL,
            amount REAL,
            consumption REAL,
            paid BOOLEAN DEFAULT 0,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (utility_id) REFERENCES utility_rates (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        conn.commit()
        print("✅ База данных инициализирована")

        # Заполняем начальными данными
        populate_categories(conn)
        add_utilities_data(conn)  # Теперь эта функция добавит утилиты только один раз
        add_admin_user(conn)

def add_admin_user(conn):
    """Добавляем администратора по умолчанию"""
    admin_username = "admin"
    admin_password = "admin123"

    # Проверяем, нет ли уже администратора
    existing = conn.execute('SELECT id FROM users WHERE username = ?', (admin_username,)).fetchone()

    if not existing:
        hashed_password = hash_password(admin_password)
        conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (admin_username, 'admin@example.com', hashed_password)
        )
        conn.commit()
        print("✅ Добавлен администратор (логин: admin, пароль: admin123)")

def populate_categories(conn):
    """Заполняем таблицу категорий начальными данными"""
    categories = [
        ('Зарплата', 'income', '💼', '#28a745'),
        ('Инвестиции', 'income', '📈', '#20c997'),
        ('Подарки', 'income', '🎁', '#fd7e14'),
        ('Прочее', 'income', '💰', '#6f42c1'),
        ('Продукты', 'expense', '🛒', '#dc3545'),
        ('Транспорт', 'expense', '🚗', '#17a2b8'),
        ('Развлечения', 'expense', '🎬', '#e83e8c'),
        ('Коммунальные услуги', 'expense', '🏠', '#6610f2'),
        ('Здоровье', 'expense', '🏥', '#20c997'),
        ('Одежда', 'expense', '👕', '#fd7e14'),
        ('Образование', 'expense', '📚', '#6f42c1'),
        ('Кредит', 'expense', '💳', '#dc3545'),
        ('Сбережения', 'expense', '💰', '#28a745')
    ]

    for name, type_, icon, color in categories:
        existing = conn.execute('SELECT id FROM categories WHERE name = ?', (name,)).fetchone()
        if not existing:
            conn.execute(
                'INSERT INTO categories (name, type, icon, color) VALUES (?, ?, ?, ?)',
                (name, type_, icon, color)
            )
            print(f"✅ Добавлена категория: {name}")

    conn.commit()

def add_utilities_data(conn):
    """Добавляем данные по коммунальным услугам только если их нет вообще в системе"""
    utilities = [
        ('Электричество', 5.5, 'кВт·ч'),
        ('Газ', 7.2, 'м³'),
        ('Вода', 40.3, 'м³'),
        ('Отопление', 1800, 'месяц'),
        ('Интернет', 500, 'месяц'),
        ('Телевидение', 300, 'месяц')
    ]

    # Добавляем услуги ТОЛЬКО если они еще не существуют вообще (без учета пользователя)
    for utility_name, rate, unit in utilities:
        # Проверяем, есть ли такая услуга в системе (без учета user_id)
        existing = conn.execute(
            'SELECT id FROM utility_rates WHERE utility_name = ?',
            (utility_name,)
        ).fetchone()

        if not existing:
            # Вставляем услугу без указания user_id (будет NULL)
            conn.execute(
                'INSERT INTO utility_rates (utility_name, rate_per_unit, unit) VALUES (?, ?, ?)',
                (utility_name, rate, unit)
            )
            print(f"✅ Добавлена услуга: {utility_name}")

    conn.commit()

def register_context_processors(app):
    app.context_processor(utility_processor)
