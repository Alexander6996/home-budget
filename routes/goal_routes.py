from datetime import datetime

from flask import redirect, render_template, request, session, url_for, flash

from auth_utils import login_required
from database import get_db_connection


def register_goal_routes(app):
    @app.route('/goals')
    @login_required
    def view_goals():
        """Просмотр целей накопления"""
        with get_db_connection() as conn:
            goals_rows = conn.execute(
                'SELECT * FROM goals WHERE user_id = ? ORDER BY created_at DESC',
                (session['user_id'],)
            ).fetchall()

            goals = []
            for row in goals_rows:
                goal = dict(row)
                try:
                    goal['current_amount'] = float(goal['current_amount']) if goal['current_amount'] else 0.0
                    goal['target_amount'] = float(goal['target_amount']) if goal['target_amount'] else 0.0
                except Exception:
                    goal['current_amount'] = 0.0
                    goal['target_amount'] = 0.0
                goals.append(goal)

            print(f"DEBUG: Передаю {len(goals)} целей в шаблон")

        return render_template('goals.html', goals=goals)

    @app.route('/add_goal', methods=['POST'])
    @login_required
    def add_goal():
        """Добавление цели накопления"""
        try:
            name = request.form['name']
            target_amount = float(request.form.get('target_amount', 0))
            deadline = request.form.get('deadline')

            if target_amount <= 0:
                flash('Целевая сумма должна быть больше 0', 'error')
                return redirect(url_for('view_goals'))

            with get_db_connection() as conn:
                conn.execute('''
                    INSERT INTO goals (name, target_amount, deadline, user_id)
                    VALUES (?, ?, ?, ?)
                ''', (name, target_amount, deadline, session['user_id']))
                conn.commit()
                flash('Цель успешно добавлена!', 'success')

        except Exception as e:
            print(f"Ошибка при добавлении цели: {e}")
            flash('Ошибка при добавлении цели', 'error')

        return redirect(url_for('view_goals'))

    @app.route('/deposit_to_goal', methods=['POST'])
    @login_required
    def deposit_to_goal():
        """Пополнение цели накопления + запись в транзакции"""
        goal_id = request.form['goal_id']
        amount = float(request.form['amount'])

        with get_db_connection() as conn:
            goal = conn.execute(
                'SELECT * FROM goals WHERE id = ? AND user_id = ?',
                (goal_id, session['user_id'])
            ).fetchone()

            if not goal:
                flash('Цель не найдена', 'error')
                return redirect(url_for('view_goals'))

            conn.execute('''
                UPDATE goals
                SET current_amount = current_amount + ?
                WHERE id = ? AND user_id = ?
            ''', (amount, goal_id, session['user_id']))

            savings_category = conn.execute('''
                SELECT id FROM categories
                WHERE name = ? AND type = 'expense'
                LIMIT 1
            ''', ('Сбережения',)).fetchone()

            if savings_category:
                conn.execute('''
                    INSERT INTO transactions (type, amount, category_id, description, date, user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    'expense',
                    amount,
                    savings_category['id'],
                    f'Пополнение цели: {goal["name"]}',
                    datetime.now().strftime('%Y-%m-%d'),
                    session['user_id']
                ))

            conn.commit()
            flash('Цель успешно пополнена!', 'success')

        return redirect(url_for('view_goals'))

    @app.route('/update_goal_progress', methods=['POST'])
    @login_required
    def update_goal_progress():
        """Обновление цели (реактивация выполненной)"""
        goal_id = request.form.get('goal_id')
        target_amount = float(request.form.get('target_amount', 0))
        action = request.form.get('action')

        if action == 'reactivate':
            with get_db_connection() as conn:
                conn.execute('''
                    UPDATE goals
                    SET current_amount = 0, target_amount = ?
                    WHERE id = ? AND user_id = ?
                ''', (target_amount, goal_id, session['user_id']))
                conn.commit()
                flash('Цель успешно реактивирована!', 'success')

        return redirect(url_for('view_goals'))

    @app.route('/update_goal', methods=['POST'])
    @login_required
    def update_goal():
        """Обновление цели (реактивация выполненной)"""
        goal_id = request.form.get('goal_id')
        target_amount = float(request.form.get('target_amount', 0))
        action = request.form.get('action')

        if action == 'reactivate':
            with get_db_connection() as conn:
                conn.execute('''
                    UPDATE goals
                    SET current_amount = 0, target_amount = ?
                    WHERE id = ? AND user_id = ?
                ''', (target_amount, goal_id, session['user_id']))
                conn.commit()
                flash('Цель успешно реактивирована!', 'success')

        return redirect(url_for('view_goals'))

    @app.route('/delete_goal/<int:goal_id>', methods=['POST'])
    @login_required
    def delete_goal(goal_id):
        """Удаление цели накопления"""
        with get_db_connection() as conn:
            conn.execute(
                'DELETE FROM goals WHERE id = ? AND user_id = ?',
                (goal_id, session['user_id'])
            )
            conn.commit()
            flash('Цель успешно удалена!', 'success')

        return redirect(url_for('view_goals'))