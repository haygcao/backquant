#!/opt/anaconda3/bin/python3
#coding: utf8

from .config import CONFIG


def create_app(config_name):
    from .api.login_api import bp_login
    from .api.backtest_api import bp_backtest
    from .api.research_api import bp_research
    from .api.system_api import bp_system
    from .api.market_data_api import bp_market_data
    from .api.packages_api import bp_packages
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
    app.register_blueprint(bp_packages)

    try:
        with app.app_context():
            ensure_default_demo_strategy()
            # Initialize market data database before scheduler
            from .market_data.db_init import init_database
            from .market_data.utils import get_market_data_db_path
            from .api.packages_api import refresh_packages_cache
            db_path = get_market_data_db_path()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            init_database(db_path)
            init_scheduler()
            # Initialize Python packages cache
            refresh_packages_cache()
    except Exception:
        app.logger.exception("failed to initialize app")

    return app
