from flask import flash, redirect, render_template, request, session, url_for

from auth_utils import hash_password, verify_password
from database import get_db_connection


def register_auth_routes(app):
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form['username']
            email = request.form.get('email', '').strip()  # Получаем email и убираем пробелы
            if email == '':
                email = None

            password = request.form['password']
            confirm_password = request.form['confirm_password']

            if password != confirm_password:
                flash('Пароли не совпадают', 'error')
                return redirect(url_for('register'))

            with get_db_connection() as conn:
                # Проверка username
                existing_user = conn.execute(
                    'SELECT id FROM users WHERE username = ?',
                    (username,)
                ).fetchone()

                if existing_user:
                    flash('Пользователь с таким именем уже существует', 'error')
                    return redirect(url_for('register'))

                # Проверка email ТОЛЬКО если он введён
                if email is not None:
                    existing_email = conn.execute(
                        'SELECT id FROM users WHERE email = ?',
                        (email,)
                    ).fetchone()

                    if existing_email:
                        flash('Пользователь с таким email уже существует', 'error')
                        return redirect(url_for('register'))

                # Создание пользователя
                hashed_password = hash_password(password)
                conn.execute(
                    'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                    (username, email, hashed_password)
                )
                conn.commit()

            flash('Регистрация успешна! Теперь войдите в систему.', 'success')
            return redirect(url_for('login'))

        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            with get_db_connection() as conn:
                user = conn.execute(
                    'SELECT id, username, password_hash FROM users WHERE username = ?',
                    (username,)
                ).fetchone()

                if user and verify_password(password, user['password_hash']):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    flash('Вы успешно вошли в систему!', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('Неверное имя пользователя или пароль', 'error')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Вы вышли из системы', 'info')
        return redirect(url_for('login'))

