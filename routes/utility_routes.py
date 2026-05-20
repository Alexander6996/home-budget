from datetime import datetime

from flask import redirect, render_template, request, session, url_for, flash

from auth_utils import login_required
from database import get_db_connection


def register_utility_routes(app):
    @app.route('/utilities')
    @login_required
    def view_utilities():
        """Просмотр коммунальных услуг"""
        with get_db_connection() as conn:
            utilities_rows = conn.execute('''
                SELECT * FROM utility_rates
                WHERE user_id IS NULL OR user_id = ?
                ORDER BY utility_name
            ''', (session['user_id'],)).fetchall()

            utilities = [dict(row) for row in utilities_rows]

            readings_rows = conn.execute('''
                SELECT ur.*, u.utility_name, u.unit
                FROM utility_readings ur
                JOIN utility_rates u ON ur.utility_id = u.id
                WHERE ur.user_id = ?
                ORDER BY ur.reading_date DESC
            ''', (session['user_id'],)).fetchall()

            readings = [dict(row) for row in readings_rows]

        return render_template('utilities.html', utilities=utilities, readings=readings)

    @app.route('/update_utility', methods=['POST'])
    @login_required
    def update_utility():
        """Обновление тарифа коммунальной услуги"""
        utility_id = request.form['utility_id']
        rate_per_unit = float(request.form['rate_per_unit'])

        with get_db_connection() as conn:
            utility = conn.execute('''
                SELECT id FROM utility_rates
                WHERE id = ? AND (user_id IS NULL OR user_id = ?)
            ''', (utility_id, session['user_id'])).fetchone()

            if not utility:
                flash('Услуга не найдена или недоступна', 'error')
                return redirect(url_for('view_utilities'))

            conn.execute('''
                UPDATE utility_rates SET rate_per_unit = ?
                WHERE id = ?
            ''', (rate_per_unit, utility_id))
            conn.commit()
            flash('Тариф успешно обновлен!', 'success')

        return redirect(url_for('view_utilities'))

    @app.route('/add_utility_reading', methods=['POST'])
    @login_required
    def add_utility_reading():
        """Добавление показаний счетчиков"""
        try:
            utility_id = request.form['utility_id']
            reading = float(request.form['reading'])
            reading_date = request.form['reading_date']
        except (KeyError, ValueError):
            flash('Неверные данные формы', 'error')
            return redirect(url_for('view_utilities'))

        with get_db_connection() as conn:
            utility = conn.execute('''
                SELECT rate_per_unit, unit FROM utility_rates
                WHERE id = ? AND (user_id IS NULL OR user_id = ?)
            ''', (utility_id, session['user_id'])).fetchone()

            if not utility:
                flash('Услуга не найдена или недоступна', 'error')
                return redirect(url_for('view_utilities'))

            prev_reading = conn.execute('''
                SELECT reading FROM utility_readings
                WHERE utility_id = ? AND user_id = ?
                ORDER BY reading_date DESC LIMIT 1
            ''', (utility_id, session['user_id'])).fetchone()

            consumption = 0
            if prev_reading:
                consumption = reading - prev_reading['reading']
                if consumption < 0:
                    flash('Новые показания меньше предыдущих!', 'error')
                    return redirect(url_for('view_utilities'))
            else:
                consumption = reading

            amount = consumption * utility['rate_per_unit']

            conn.execute('''
                INSERT INTO utility_readings
                (utility_id, reading, reading_date, amount, consumption, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (utility_id, reading, reading_date, amount, consumption, session['user_id']))

            conn.commit()
            flash('Показания успешно добавлены!', 'success')

        return redirect(url_for('view_utilities'))

    @app.route('/mark_paid/<int:reading_id>')
    @login_required
    def mark_paid(reading_id):
        """Отметка оплаты коммунальной услуги + запись в транзакции"""
        with get_db_connection() as conn:
            reading = conn.execute('''
                SELECT ur.*, u.utility_name
                FROM utility_readings ur
                JOIN utility_rates u ON ur.utility_id = u.id
                WHERE ur.id = ? AND ur.user_id = ?
            ''', (reading_id, session['user_id'])).fetchone()

            if not reading:
                flash('Запись не найдена', 'error')
                return redirect(url_for('view_utilities'))

            if reading['paid']:
                flash('Эта услуга уже отмечена как оплаченная', 'info')
                return redirect(url_for('view_utilities'))

            conn.execute('''
                UPDATE utility_readings
                SET paid = 1
                WHERE id = ? AND user_id = ?
            ''', (reading_id, session['user_id']))

            utilities_category = conn.execute('''
                SELECT id FROM categories
                WHERE name = ? AND type = 'expense'
                LIMIT 1
            ''', ('Коммунальные услуги',)).fetchone()

            if utilities_category:
                conn.execute('''
                    INSERT INTO transactions (type, amount, category_id, description, date, user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    'expense',
                    reading['amount'],
                    utilities_category['id'],
                    f'Оплата коммунальной услуги: {reading["utility_name"]}',
                    datetime.now().strftime('%Y-%m-%d'),
                    session['user_id']
                ))

            conn.commit()
            flash('Оплата отмечена!', 'success')

        return redirect(url_for('view_utilities'))