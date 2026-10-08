import os
import sys
import tempfile
import pytest

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db


@pytest.fixture(scope="session")
def test_db():
    # Use temporary sqlite file for testing
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Patch global SessionLocal
    import app.database
    import app.services.job_processor
    original_session_local = app.database.SessionLocal
    app.database.SessionLocal = TestingSessionLocal
    app.services.job_processor.SessionLocal = TestingSessionLocal

    yield TestingSessionLocal, engine

    app.database.SessionLocal = original_session_local
    app.services.job_processor.SessionLocal = original_session_local

    try:
        os.remove(db_path)
    except Exception:
        pass


@pytest.fixture
def client(test_db):
    TestingSessionLocal, _ = test_db

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
