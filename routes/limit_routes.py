from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime, timedelta

from auth_utils import login_required
from database import get_db_connection

limit_bp = Blueprint('limits', __name__)


@limit_bp.route('/limits')
@login_required
def view_limits():
    """Просмотр лимитов расходов"""
    with get_db_connection() as conn:
        current_month = datetime.now().strftime('%Y-%m')
        today = datetime.now()

        # Получаем все категории расходов
        categories_rows = conn.execute(
            'SELECT * FROM categories WHERE type = "expense" ORDER BY name'
        ).fetchall()

        # Преобразуем Row в dict и добавляем информацию о лимитах
        categories = []
        for row in categories_rows:
            category = dict(row)

            # Получаем лимит на текущий месяц
            limit = conn.execute('''
                SELECT id, amount_limit, period
                FROM limits
                WHERE category_id = ? AND month_year = ? AND user_id = ?
            ''', (category['id'], current_month, session['user_id'])).fetchone()

            if limit:
                category['limit_id'] = limit['id']
                category['amount_limit'] = limit['amount_limit']
                category['period'] = limit['period'] if limit['period'] else 'monthly'

                # Определяем даты периода
                if category['period'] == 'monthly':
                    start_date = today.replace(day=1).strftime('%Y-%m-%d')
                    end_date = today.strftime('%Y-%m-%d')
                elif category['period'] == 'weekly':
                    start_of_week = today - timedelta(days=today.weekday())
                    end_of_week = start_of_week + timedelta(days=6)
                    start_date = start_of_week.strftime('%Y-%m-%d')
                    end_date = end_of_week.strftime('%Y-%m-%d')
                elif category['period'] == 'daily':
                    start_date = today.strftime('%Y-%m-%d')
                    end_date = start_date
                else:
                    start_date = today.replace(day=1).strftime('%Y-%m-%d')
                    end_date = today.strftime('%Y-%m-%d')

                # Считаем потраченную сумму
                spent_result = conn.execute('''
                    SELECT SUM(amount) as total
                    FROM transactions
                    WHERE category_id = ? AND user_id = ?
                      AND date BETWEEN ? AND ?
                ''', (category['id'], session['user_id'], start_date, end_date)).fetchone()

                category['current_spent'] = spent_result['total'] if spent_result['total'] else 0
            else:
                category['limit_id'] = None
                category['amount_limit'] = None
                category['period'] = None
                category['current_spent'] = 0

            categories.append(category)

    return render_template('limits.html', categories=categories)


@limit_bp.route('/set_limit', methods=['POST'])
@login_required
def set_limit():
    """Установка лимита расходов"""
    try:
        category_id = request.form['category_id']
        amount_limit = float(request.form.get('amount_limit', 0))
        period = request.form.get('period', 'monthly')
    except (KeyError, ValueError):
        flash('Неверные данные формы', 'error')
        return redirect(url_for('view_limits'))

    with get_db_connection() as conn:
        current_month = datetime.now().strftime('%Y-%m')

        existing = conn.execute('''
            SELECT id
            FROM limits
            WHERE category_id = ? AND month_year = ? AND user_id = ?
        ''', (category_id, current_month, session['user_id'])).fetchone()

        if existing:
            conn.execute('''
                UPDATE limits
                SET amount_limit = ?, period = ?
                WHERE id = ? AND user_id = ?
            ''', (amount_limit, period, existing['id'], session['user_id']))
        else:
            conn.execute('''
                INSERT INTO limits (category_id, amount_limit, period, month_year, user_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (category_id, amount_limit, period, current_month, session['user_id']))

        conn.commit()
        flash('Лимит успешно установлен!', 'success')

    return redirect(url_for('view_limits'))


@limit_bp.route('/update_limit', methods=['POST'])
@login_required
def update_limit():
    """Редактирование существующего лимита"""
    try:
        category_id = request.form['category_id']
        amount_limit = float(request.form.get('amount_limit', 0))
        period = request.form.get('period', 'monthly')
    except (KeyError, ValueError):
        flash('Неверные данные формы', 'error')
        return redirect(url_for('view_limits'))

    with get_db_connection() as conn:
        current_month = datetime.now().strftime('%Y-%m')

        conn.execute('''
            UPDATE limits
            SET amount_limit = ?, period = ?
            WHERE category_id = ? AND month_year = ? AND user_id = ?
        ''', (amount_limit, period, category_id, current_month, session['user_id']))

        conn.commit()
        flash('Лимит успешно обновлен!', 'success')

    return redirect(url_for('view_limits'))


@limit_bp.route('/delete_limit/<int:limit_id>', methods=['POST', 'GET'])
@login_required
def delete_limit(limit_id):
    """Удаление лимита расходов"""
    with get_db_connection() as conn:
        limit = conn.execute(
            'SELECT id FROM limits WHERE id = ? AND user_id = ?',
            (limit_id, session['user_id'])
        ).fetchone()

        if limit:
            conn.execute('DELETE FROM limits WHERE id = ?', (limit_id,))
            conn.commit()
            flash('Лимит успешно удален!', 'success')
        else:
            flash('Лимит не найден или у вас нет прав на его удаление', 'error')

    return redirect(url_for('view_limits'))


@limit_bp.route('/api/limits_stats')
@login_required
def limits_stats():
    """API для получения статистики лимитов"""
    with get_db_connection() as conn:
        current_month = datetime.now().strftime('%Y-%m')
        today = datetime.now()

        limits = conn.execute('''
            SELECT l.*, c.name as category_name, c.icon as category_icon
            FROM limits l
            JOIN categories c ON l.category_id = c.id
            WHERE l.month_year = ? AND l.user_id = ?
        ''', (current_month, session['user_id'])).fetchall()

        stats = {
            'total_limits': len(limits),
            'total_limit_amount': 0,
            'total_spent': 0,
            'warnings': [],
            'over_limit': []
        }

        for limit in limits:
            if limit['period'] == 'monthly':
                start_date = today.replace(day=1).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            elif limit['period'] == 'weekly':
                start_of_week = today - timedelta(days=today.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                start_date = start_of_week.strftime('%Y-%m-%d')
                end_date = end_of_week.strftime('%Y-%m-%d')
            elif limit['period'] == 'daily':
                start_date = today.strftime('%Y-%m-%d')
                end_date = start_date
            else:
                start_date = today.replace(day=1).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')

            spent_result = conn.execute('''
                SELECT SUM(amount) as total
                FROM transactions
                WHERE category_id = ? AND user_id = ?
                  AND date BETWEEN ? AND ?
            ''', (limit['category_id'], session['user_id'], start_date, end_date)).fetchone()

            spent = spent_result['total'] if spent_result['total'] else 0
            percentage = (spent / limit['amount_limit'] * 100) if limit['amount_limit'] > 0 else 0

            stats['total_limit_amount'] += limit['amount_limit']
            stats['total_spent'] += spent

            if percentage >= 70:
                stats['warnings'].append({
                    'category': limit['category_name'],
                    'percentage': round(percentage, 1),
                    'spent': spent,
                    'limit': limit['amount_limit']
                })

            if percentage >= 100:
                stats['over_limit'].append({
                    'category': limit['category_name'],
                    'exceeded': spent - limit['amount_limit']
                })

        return jsonify(stats)


def register_limit_routes(app):
    app.register_blueprint(limit_bp)