from functools import wraps
import hashlib
import secrets

from flask import flash, redirect, session, url_for


def hash_password(password):
    """Хеширование пароля"""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((password + salt).encode())
    return f"{hash_obj.hexdigest()}:{salt}"

def verify_password(password, hashed_password):
    """Проверка пароля"""
    stored_hash, salt = hashed_password.split(':')
    hash_obj = hashlib.sha256((password + salt).encode())
    return hash_obj.hexdigest() == stored_hash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function
