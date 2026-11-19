from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False, "timeout": 15},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")  # SQLite ignores foreign keys unless asked
    cursor.close()


def init_db():
    # Creates missing tables. It does NOT change existing ones: for that we'll add
    # migrations (Alembic) once the schema needs to change with real data in it.
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
