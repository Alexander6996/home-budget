from flask import Flask
import os
import pytz
from datetime import datetime

from database import init_db
from routes.auth_routes import register_auth_routes
from routes.main_routes import register_main_routes
from routes.transaction_routes import register_transaction_routes
from routes.statistics_routes import register_statistics_routes
from routes.limit_routes import register_limit_routes
from routes.goal_routes import register_goal_routes
from routes.utility_routes import register_utility_routes
from routes.monthly_payment_routes import register_monthly_routes


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["DATABASE"] = "budget.db"


def get_moscow_time():
    moscow_tz = pytz.timezone("Europe/Moscow")
    return datetime.now(moscow_tz)


@app.context_processor
def utility_processor():
    return dict(get_moscow_time=get_moscow_time)


def add_legacy_route_aliases(app_instance):
    aliases = [
        ("index", "/", "main.index", ["GET"]),
        ("set_monthly_budget", "/set_monthly_budget", "main.set_monthly_budget", ["POST"]),

        ("login", "/login", "auth.login", ["GET", "POST"]),
        ("register", "/register", "auth.register", ["GET", "POST"]),
        ("logout", "/logout", "auth.logout", ["GET"]),

        ("add_transaction", "/add", "transactions.add_transaction", ["GET", "POST"]),
        ("view_transactions", "/transactions", "transactions.view_transactions", ["GET"]),
        ("edit_transaction", "/edit/<int:transaction_id>", "transactions.edit_transaction", ["GET", "POST"]),
        ("delete_transaction", "/delete/<int:transaction_id>", "transactions.delete_transaction", ["GET"]),
        ("export_excel", "/export/excel", "transactions.export_excel", ["GET"]),
        ("quick_add", "/quick_add", "transactions.quick_add", ["POST"]),

        ("statistics", "/statistics", "statistics.statistics", ["GET"]),
        ("statistics_year", "/statistics/year/<int:year>", "statistics.statistics_year", ["GET"]),
        ("statistics_daily", "/statistics/day/<int:year>/<int:month>", "statistics.statistics_daily", ["GET"]),

        ("view_limits", "/limits", "limits.view_limits", ["GET"]),
        ("set_limit", "/set_limit", "limits.set_limit", ["POST"]),
        ("update_limit", "/update_limit", "limits.update_limit", ["POST"]),
        ("delete_limit", "/delete_limit/<int:limit_id>", "limits.delete_limit", ["POST", "GET"]),
        ("limits_stats", "/api/limits_stats", "limits.limits_stats", ["GET"]),

        ("view_goals", "/goals", "goals.view_goals", ["GET"]),
        ("add_goal", "/add_goal", "goals.add_goal", ["POST"]),
        ("deposit_to_goal", "/deposit_to_goal", "goals.deposit_to_goal", ["POST"]),
        ("delete_goal", "/delete_goal/<int:goal_id>", "goals.delete_goal", ["GET", "POST"]),

        ("view_utilities", "/utilities", "utilities.view_utilities", ["GET"]),
        ("update_utility", "/update_utility", "utilities.update_utility", ["POST"]),
        ("add_utility_reading", "/add_utility_reading", "utilities.add_utility_reading", ["POST"]),
        ("mark_paid", "/mark_paid/<int:reading_id>", "utilities.mark_paid", ["GET"]),
    ]

    for old_endpoint, rule, new_endpoint, methods in aliases:
        if new_endpoint in app_instance.view_functions and old_endpoint not in app_instance.view_functions:
            app_instance.add_url_rule(
                rule,
                endpoint=old_endpoint,
                view_func=app_instance.view_functions[new_endpoint],
                methods=methods
            )


register_auth_routes(app)
register_main_routes(app)
register_transaction_routes(app)
register_statistics_routes(app)
register_limit_routes(app)
register_goal_routes(app)
register_utility_routes(app)
register_monthly_routes(app)

add_legacy_route_aliases(app)

# Инициализация базы должна вызываться и при запуске через gunicorn
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)