import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "certificates.db").replace("\\", "/")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# connect_args={"check_same_thread": False} is required only for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency yielding a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_compatibility(db_engine):
    """
    Lightweight, automatic SQLite schema migration.
    Inspects existing tables and automatically adds missing columns
    (e.g., idempotency_key, total, successful, failed, updated_at)
    without dropping user data or raising OperationalErrors.
    """
    try:
        with db_engine.connect() as conn:
            # 1. Check generation_jobs columns
            cursor = conn.exec_driver_sql("PRAGMA table_info(generation_jobs)")
            cols = {row[1] for row in cursor.fetchall()}
            if cols:
                if "idempotency_key" not in cols:
                    conn.exec_driver_sql("ALTER TABLE generation_jobs ADD COLUMN idempotency_key VARCHAR(100)")
                if "total" not in cols:
                    conn.exec_driver_sql("ALTER TABLE generation_jobs ADD COLUMN total INTEGER DEFAULT 0 NOT NULL")
                    if "total_count" in cols:
                        conn.exec_driver_sql("UPDATE generation_jobs SET total = total_count")
                if "successful" not in cols:
                    conn.exec_driver_sql("ALTER TABLE generation_jobs ADD COLUMN successful INTEGER DEFAULT 0 NOT NULL")
                    if "processed_count" in cols:
                        conn.exec_driver_sql("UPDATE generation_jobs SET successful = processed_count")
                if "failed" not in cols:
                    conn.exec_driver_sql("ALTER TABLE generation_jobs ADD COLUMN failed INTEGER DEFAULT 0 NOT NULL")
                    if "failed_count" in cols:
                        conn.exec_driver_sql("UPDATE generation_jobs SET failed = failed_count")

            # 2. Check certificates columns
            cursor2 = conn.exec_driver_sql("PRAGMA table_info(certificates)")
            cols2 = {row[1] for row in cursor2.fetchall()}
            if cols2:
                if "updated_at" not in cols2:
                    conn.exec_driver_sql("ALTER TABLE certificates ADD COLUMN updated_at DATETIME")

            conn.commit()
    except Exception:
        # Ignore for in-memory or already up-to-date engines
        pass
