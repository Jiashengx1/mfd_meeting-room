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
        conn.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS campus VARCHAR(20)"))
        conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS campus VARCHAR(20)"))
        conn.execute(text("ALTER TABLE recurring_series ADD COLUMN IF NOT EXISTS campus VARCHAR(20)"))
        conn.execute(text("UPDATE rooms SET campus = '庆春' WHERE campus IS NULL OR campus = ''"))
        conn.execute(
            text(
                """
                UPDATE bookings
                SET campus = rooms.campus
                FROM rooms
                WHERE bookings.room_id = rooms.id
                  AND (bookings.campus IS NULL OR bookings.campus = '')
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE recurring_series
                SET campus = rooms.campus
                FROM rooms
                WHERE recurring_series.room_id = rooms.id
                  AND (recurring_series.campus IS NULL OR recurring_series.campus = '')
                """
            )
        )
        for table in ("rooms", "bookings", "recurring_series"):
            conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN campus SET DEFAULT '庆春'"))
            conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN campus SET NOT NULL"))
        conn.execute(text("DROP INDEX IF EXISTS ix_rooms_name"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_rooms_name ON rooms (name)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_rooms_campus ON rooms (campus)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_bookings_campus ON bookings (campus)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_recurring_series_campus ON recurring_series (campus)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_rooms_campus_name ON rooms (campus, name)"))
        for table in ("rooms", "bookings", "recurring_series"):
            constraint_name = f"ck_{table}_campus"
            conn.execute(
                text(
                    f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = '{constraint_name}'
                        ) THEN
                            ALTER TABLE {table}
                            ADD CONSTRAINT {constraint_name}
                            CHECK (campus IN ('庆春', '钱塘', '大运河', '绍兴'));
                        END IF;
                    END $$;
                    """
                )
            )
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
