from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS department VARCHAR(100)"))
        conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS user_name VARCHAR(100)"))
        conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS recurring_series_id INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_bookings_recurring_series_id ON bookings (recurring_series_id)"))
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_bookings_recurring_series_id'
                    ) THEN
                        ALTER TABLE bookings
                        ADD CONSTRAINT fk_bookings_recurring_series_id
                        FOREIGN KEY (recurring_series_id) REFERENCES recurring_series(id);
                    END IF;
                END $$;
                """
            )
        )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'no_overlapping_active_bookings'
                    ) THEN
                        ALTER TABLE bookings
                        ADD CONSTRAINT no_overlapping_active_bookings
                        EXCLUDE USING gist (
                            room_id WITH =,
                            tstzrange(start_at, end_at, '[)') WITH &&
                        )
                        WHERE (status = 'active');
                    END IF;
                END $$;
                """
            )
        )
