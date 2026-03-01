#!/usr/bin/env python3
"""Test script for database abstraction layer."""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask
from app.config import CONFIG
from app.database import get_db_connection, get_db_type


def test_database_abstraction():
    """Test database abstraction layer with SQLite."""
    print("=" * 60)
    print("Testing Database Abstraction Layer")
    print("=" * 60)

    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(CONFIG['production'])

    with app.app_context():
        # Test 1: Get database type
        print("\n[Test 1] Get database type")
        db_type = get_db_type()
        print(f"✓ Database type: {db_type}")
        assert db_type == 'sqlite', f"Expected 'sqlite', got '{db_type}'"

        # Test 2: Connect to market_data database
        print("\n[Test 2] Connect to market_data database")
        with get_db_connection('market_data') as db:
            print(f"✓ Connected to: {db.config.sqlite_path}")

            # Test 3: Query tables
            print("\n[Test 3] Query database tables")
            tables = db.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            print(f"✓ Found {len(tables)} tables:")
            for table in tables:
                print(f"  - {table['name']}")

            # Test 4: Query market_data_tasks
            print("\n[Test 4] Query market_data_tasks table")
            result = db.fetchone(
                "SELECT COUNT(*) as count FROM market_data_tasks"
            )
            print(f"✓ Tasks count: {result['count']}")

            # Test 5: Query cron config
            print("\n[Test 5] Query cron config")
            config_row = db.fetchone(
                "SELECT * FROM market_data_cron_config WHERE id = 1"
            )
            if config_row:
                print(f"✓ Cron enabled: {config_row['enabled']}")
                print(f"✓ Cron expression: {config_row['cron_expression']}")
            else:
                print("✓ No cron config found (expected for new install)")

        # Test 6: Connect to auth database
        print("\n[Test 6] Connect to auth database")
        with get_db_connection('auth') as db:
            print(f"✓ Connected to: {db.config.sqlite_path}")

            # Query users
            result = db.fetchone("SELECT COUNT(*) as count FROM users")
            print(f"✓ Users count: {result['count']}")

        # Test 7: Connect to backtest_meta database
        print("\n[Test 7] Connect to backtest_meta database")
        with get_db_connection('backtest_meta') as db:
            print(f"✓ Connected to: {db.config.sqlite_path}")

            # Query rename mappings
            tables = db.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            print(f"✓ Found {len(tables)} tables")

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == '__main__':
    try:
        test_database_abstraction()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
