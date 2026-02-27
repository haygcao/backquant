#!/opt/anaconda3/bin/python3
#coding: utf8

from .config import CONFIG


def create_app(config_name):
    from .api.login_api import bp_login
    from .api.backtest_api import bp_backtest
    from .api.research_api import bp_research
    from .api.system_api import bp_system
    from .api.market_data_api import bp_market_data
    from .backtest.services.runner import ensure_default_demo_strategy
    from .market_data.scheduler import init_scheduler
    from flask import Flask
    from flask_cors import CORS

    app = Flask(__name__)
    CORS(app, supports_credentials=True)
    app.config.from_object(CONFIG[config_name])

    app.register_blueprint(bp_login)
    app.register_blueprint(bp_backtest)
    app.register_blueprint(bp_research)
    app.register_blueprint(bp_system)
    app.register_blueprint(bp_market_data)

    try:
        with app.app_context():
            ensure_default_demo_strategy()
            # Initialize market data database before scheduler
            from .market_data.db_init import init_database
            from pathlib import Path
            db_path = Path(__file__).parent.parent / "data" / "market_data.sqlite3"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            init_database(db_path)
            init_scheduler()
    except Exception:
        app.logger.exception("failed to initialize app")

    return app
