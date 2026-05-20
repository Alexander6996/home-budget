from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta

from auth_utils import login_required
from database import get_db_connection

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    """Главная страница"""
    with get_db_connection() as conn:
        current_month = datetime.now().strftime('%Y-%m')
        today = datetime.now()

        # Доходы за текущий месяц
        income_result = conn.execute('''
            SELECT SUM(amount) as total
            FROM transactions
            WHERE type = 'income'
              AND strftime('%Y-%m', date) = ?
              AND user_id = ?
        ''', (current_month, session['user_id'])).fetchone()
        income = income_result['total'] if income_result['total'] else 0

        # Расходы за текущий месяц
        expense_result = conn.execute('''
            SELECT SUM(amount) as total
            FROM transactions
            WHERE type = 'expense'
              AND strftime('%Y-%m', date) = ?
              AND user_id = ?
        ''', (current_month, session['user_id'])).fetchone()
        expense = expense_result['total'] if expense_result['total'] else 0

        # Баланс
        balance = income - expense

        # Общий бюджет на месяц
        budget_row = conn.execute('''
            SELECT amount
            FROM monthly_budgets
            WHERE user_id = ? AND month_year = ?
        ''', (session['user_id'], current_month)).fetchone()

        monthly_budget = budget_row['amount'] if budget_row else 0
        budget_spent = expense
        budget_remaining = monthly_budget - budget_spent if monthly_budget else 0
        budget_percent = (budget_spent / monthly_budget * 100) if monthly_budget > 0 else 0

        # Последние 5 транзакций
        transactions = conn.execute('''
            SELECT t.*, c.name as category_name, c.icon as category_icon
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = ?
            ORDER BY t.date DESC, t.created_at DESC
            LIMIT 5
        ''', (session['user_id'],)).fetchall()

        # Статистика по категориям расходов
        expense_categories = conn.execute('''
            SELECT c.name, c.color, SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.type = 'expense'
              AND strftime('%Y-%m', t.date) = ?
              AND t.user_id = ?
            GROUP BY c.name, c.color
            ORDER BY total DESC
        ''', (current_month, session['user_id'])).fetchall()

        # Цели накопления
        goals = conn.execute('''
            SELECT *
            FROM goals
            WHERE user_id = ?
            ORDER BY deadline
        ''', (session['user_id'],)).fetchall()

        # Напоминания о лимитах
        reminders = []
        limits = conn.execute('''
            SELECT l.*, c.name as category_name, c.icon as category_icon
            FROM limits l
            JOIN categories c ON l.category_id = c.id
            WHERE l.month_year = ? AND l.user_id = ?
        ''', (current_month, session['user_id'])).fetchall()

        for limit in limits:
            # Определяем период для расчета
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

            # Считаем потраченную сумму
            spent_result = conn.execute('''
                SELECT SUM(amount) as total
                FROM transactions
                WHERE category_id = ?
                  AND user_id = ?
                  AND date BETWEEN ? AND ?
            ''', (limit['category_id'], session['user_id'], start_date, end_date)).fetchone()

            spent = spent_result['total'] if spent_result['total'] else 0
            percentage = (spent / limit['amount_limit'] * 100) if limit['amount_limit'] > 0 else 0

            # Проверяем условия для напоминаний
            if 50 <= percentage < 80:
                reminders.append({
                    'type': 'warning',
                    'message': f'Вы потратили {percentage:.0f}% от лимита в категории "{limit["category_name"]}"',
                    'category': limit['category_name'],
                    'spent': spent,
                    'limit': limit['amount_limit'],
                    'remaining': limit['amount_limit'] - spent
                })
            elif 80 <= percentage < 100:
                reminders.append({
                    'type': 'danger',
                    'message': f'Близко к лимиту! Использовано {percentage:.0f}% в категории "{limit["category_name"]}"',
                    'category': limit['category_name'],
                    'spent': spent,
                    'limit': limit['amount_limit'],
                    'remaining': limit['amount_limit'] - spent
                })
            elif percentage >= 100:
                reminders.append({
                    'type': 'danger',
                    'message': f'Лимит превышен в категории "{limit["category_name"]}" на {spent - limit["amount_limit"]:.2f} ₽',
                    'category': limit['category_name'],
                    'spent': spent,
                    'limit': limit['amount_limit'],
                    'exceeded': spent - limit['amount_limit']
                })

    return render_template(
        'index.html',
        income=income,
        expense=expense,
        balance=balance,
        transactions=transactions,
        expense_categories=expense_categories,
        goals=goals,
        reminders=reminders,
        monthly_budget=monthly_budget,
        budget_spent=budget_spent,
        budget_remaining=budget_remaining,
        budget_percent=budget_percent
    )


@main_bp.route('/set_monthly_budget', methods=['POST'])
@login_required
def set_monthly_budget():
    """Установка общего бюджета на месяц"""
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        flash('Некорректная сумма бюджета', 'error')
        return redirect(url_for('main.index'))

    if amount <= 0:
        flash('Сумма бюджета должна быть больше нуля', 'error')
        return redirect(url_for('main.index'))

    current_month = datetime.now().strftime('%Y-%m')

    with get_db_connection() as conn:
        existing = conn.execute('''
            SELECT id
            FROM monthly_budgets
            WHERE user_id = ? AND month_year = ?
        ''', (session['user_id'], current_month)).fetchone()

        if existing:
            conn.execute('''
                UPDATE monthly_budgets
                SET amount = ?
                WHERE id = ?
            ''', (amount, existing['id']))
            flash('Общий бюджет на месяц обновлен', 'success')
        else:
            conn.execute('''
                INSERT INTO monthly_budgets (user_id, month_year, amount)
                VALUES (?, ?, ?)
            ''', (session['user_id'], current_month, amount))
            flash('Общий бюджет на месяц установлен', 'success')

        conn.commit()

    return redirect(url_for('main.index'))

def register_main_routes(app):
    app.register_blueprint(main_bp)