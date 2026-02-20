#!/opt/anaconda3/bin/python3
#coding: utf8

from .config import CONFIG


def create_app(config_name):
    from .api.login_api import bp_login
    from .api.backtest_api import bp_backtest
    from .api.research_api import bp_research
    from .backtest.services.runner import ensure_default_demo_strategy
    from flask import Flask
    from flask_cors import CORS

    app = Flask(__name__)
    CORS(app, supports_credentials=True)
    app.config.from_object(CONFIG[config_name])

    app.register_blueprint(bp_login)
    app.register_blueprint(bp_backtest)
    app.register_blueprint(bp_research)

    try:
        with app.app_context():
            ensure_default_demo_strategy()
    except Exception:
        app.logger.exception("failed to ensure default demo strategy")

    return app
