from datetime import datetime

from flask import render_template, request, session

from auth_utils import login_required
from database import get_db_connection


def register_statistics_routes(app):
    @app.route('/statistics')
    @login_required
    def statistics():
        """Страница статистики с выбором периода"""
        with get_db_connection() as conn:
            period = request.args.get('period', 'month')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            today = datetime.now()
            current_month = today.strftime('%Y-%m')
            current_year = today.strftime('%Y')

            base_where = ' WHERE t.user_id = ? '
            params = [session['user_id']]

            if period == 'month':
                base_where += " AND strftime('%Y-%m', t.date) = ? "
                params.append(current_month)
                period_title = 'за текущий месяц'
            elif period == 'year':
                base_where += " AND strftime('%Y', t.date) = ? "
                params.append(current_year)
                period_title = 'за текущий год'
            elif period == 'custom':
                if start_date:
                    base_where += ' AND t.date >= ? '
                    params.append(start_date)
                if end_date:
                    base_where += ' AND t.date <= ? '
                    params.append(end_date)
                period_title = 'за выбранный период'
            else:
                period = 'all'
                period_title = 'за все время'

            total_income_result = conn.execute(f'''
                SELECT SUM(t.amount) as total
                FROM transactions t
                {base_where}
                AND t.type = 'income'
            ''', params).fetchone()
            total_income = total_income_result['total'] if total_income_result['total'] else 0

            total_expense_result = conn.execute(f'''
                SELECT SUM(t.amount) as total
                FROM transactions t
                {base_where}
                AND t.type = 'expense'
            ''', params).fetchone()
            total_expense = total_expense_result['total'] if total_expense_result['total'] else 0

            income_by_category = conn.execute(f'''
                SELECT c.name, c.color, SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                {base_where}
                AND t.type = 'income'
                GROUP BY c.name, c.color
                ORDER BY total DESC
            ''', params).fetchall()

            expense_by_category = conn.execute(f'''
                SELECT c.name, c.color, SUM(t.amount) as total
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                {base_where}
                AND t.type = 'expense'
                GROUP BY c.name, c.color
                ORDER BY total DESC
            ''', params).fetchall()

            balance_by_day = conn.execute(f'''
                SELECT
                    t.date,
                    SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE -t.amount END) as daily_balance
                FROM transactions t
                {base_where}
                GROUP BY t.date
                ORDER BY t.date
            ''', params).fetchall()

        balance_labels = []
        balance_values = []
        running_balance = 0

        for row in balance_by_day:
            balance_labels.append(row['date'])
            running_balance += row['daily_balance'] if row['daily_balance'] else 0
            balance_values.append(round(running_balance, 2))

        return render_template(
            'statistics.html',
            total_income=total_income,
            total_expense=total_expense,
            income_by_category=income_by_category,
            expense_by_category=expense_by_category,
            balance_labels=balance_labels,
            balance_values=balance_values,
            period=period,
            period_title=period_title,
            start_date=start_date,
            end_date=end_date
        )