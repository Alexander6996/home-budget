from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import get_db_connection
from datetime import datetime

monthly_bp = Blueprint(
    "monthly",
    __name__
)


def register_monthly_routes(app):
    app.register_blueprint(monthly_bp)


@monthly_bp.route("/monthly_payments")
def view_monthly_payments():

    if "user_id" not in session:
        return redirect(url_for("login"))

    month_year = datetime.now().strftime("%Y-%m")

    with get_db_connection() as conn:

        payments = conn.execute(
            """
            SELECT
                mp.*,
                c.name as category_name,

                EXISTS(
                    SELECT 1

                    FROM monthly_payment_logs mpl

                    WHERE mpl.payment_id = mp.id
                    AND mpl.month_year = ?
                ) as paid

            FROM monthly_payments mp

            LEFT JOIN categories c
            ON mp.category_id = c.id

            WHERE mp.user_id = ?

            ORDER BY mp.payment_day
            """,

            (
                month_year,
                session["user_id"]
            )

        ).fetchall()


        categories = conn.execute(
            """
            SELECT *

            FROM categories

            WHERE type='expense'

            ORDER BY name
            """
        ).fetchall()


    return render_template(
        "monthly_payments.html",
        payments=payments,
        categories=categories
    )


@monthly_bp.route(
    "/add_monthly_payment",
    methods=["POST"]
)
def add_monthly_payment():

    if "user_id" not in session:
        return redirect(
            url_for(
                "login"
            )
        )

    with get_db_connection() as conn:

        conn.execute(
            """
            INSERT INTO monthly_payments
            (
                name,
                amount,
                category_id,
                payment_day,
                user_id
            )

            VALUES
            (
                ?,?,?,?,?
            )
            """,

            (
                request.form["name"],
                request.form["amount"],
                request.form["category_id"],
                request.form["payment_day"],
                session["user_id"]
            )
        )

        conn.commit()


    flash(
        "Платеж успешно добавлен",
        "success"
    )

    return redirect(
        url_for(
            "monthly.view_monthly_payments"
        )
    )


@monthly_bp.route(
    "/pay_monthly/<int:payment_id>"
)
def pay_monthly(payment_id):

    if "user_id" not in session:
        return redirect(
            url_for(
                "login"
            )
        )

    month_year = datetime.now().strftime(
        "%Y-%m"
    )

    with get_db_connection() as conn:

        already_paid = conn.execute(
            """
            SELECT *

            FROM monthly_payment_logs

            WHERE payment_id = ?

            AND month_year = ?
            """,

            (
                payment_id,
                month_year
            )

        ).fetchone()


        if not already_paid:

            payment = conn.execute(
                """
                SELECT *

                FROM monthly_payments

                WHERE id = ?

                AND user_id = ?
                """,

                (
                    payment_id,
                    session["user_id"]
                )

            ).fetchone()


            if payment:

                conn.execute(
                    """
                    INSERT INTO transactions
                    (
                        type,
                        amount,
                        category_id,
                        description,
                        date,
                        user_id
                    )

                    VALUES
                    (
                        'expense',
                        ?,
                        ?,
                        ?,
                        date('now'),
                        ?
                    )
                    """,

                    (
                        payment["amount"],
                        payment["category_id"],
                        f"Ежемесячный платеж: {payment['name']}",
                        session["user_id"]
                    )

                )


                conn.execute(
                    """
                    INSERT INTO monthly_payment_logs
                    (
                        payment_id,
                        month_year
                    )

                    VALUES
                    (
                        ?,?
                    )
                    """,

                    (
                        payment_id,
                        month_year
                    )

                )


                conn.commit()


    return redirect(
        url_for(
            "monthly.view_monthly_payments"
        )
    )


@monthly_bp.route(
    "/delete_monthly/<int:payment_id>"
)
def delete_monthly(payment_id):

    if "user_id" not in session:
        return redirect(
            url_for(
                "login"
            )
        )

    with get_db_connection() as conn:

        conn.execute(
            """
            DELETE FROM monthly_payment_logs

            WHERE payment_id = ?
            """,

            (
                payment_id,
            )
        )


        conn.execute(
            """
            DELETE FROM monthly_payments

            WHERE id = ?

            AND user_id = ?
            """,

            (
                payment_id,
                session["user_id"]
            )
        )

        conn.commit()


    return redirect(
        url_for(
            "monthly.view_monthly_payments"
        )
    )