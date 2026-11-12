"""Database invariants, request rollback, and the real Alembic migration path."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app import database
from app.core.config import PROJECT_ROOT, get_settings
from app.database import build_engine
from app.models import Product, Seller


@pytest.mark.parametrize(
    "invalid", [{"price": -1, "seller_id": 1}, {"price": 100, "seller_id": 999}]
)
def test_database_rejects_invalid_price_and_orphan_product(sessions, owner, invalid):
    with sessions() as db:
        db.add(Product(name="Notebook", desc="Description", **invalid))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_request_session_rolls_back_uncommitted_work(monkeypatch, sessions):
    monkeypatch.setattr(database, "SessionLocal", sessions)
    dependency = database.get_db()
    session = next(dependency)
    session.add(Seller(username="rollback", email="rollback@example.com", hashed_password="test"))
    session.flush()
    dependency.close()  # Simulates request cleanup before a commit.
    with sessions() as db:
        assert db.scalar(select(Seller).where(Seller.username == "rollback")) is None


def test_migrations_upgrade_match_models_and_downgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    engine = build_engine(url)
    try:
        # Creating/importing an engine alone must not create application tables.
        assert inspect(engine).get_table_names() == []
        command.upgrade(config, "head")
        assert set(inspect(engine).get_table_names()) == {"sellers", "products", "alembic_version"}
        command.check(config)  # Detect drift between hand-written migration and ORM.
        command.upgrade(config, "head")  # Running deployment migrations twice is safe.
        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        command.upgrade(config, "head")
    finally:
        engine.dispose()
        get_settings.cache_clear()
