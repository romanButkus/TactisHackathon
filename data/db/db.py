from sqlalchemy import create_engine, create_index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Define the SQLite database URL.
# "sqlite:///./test.db" creates a file named 'test.db' in the current directory.
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

# 2. Create the SQLAlchemy engine.
# 'connect_args={"check_same_thread": False}' is REQUIRED only for SQLite.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. Create a SessionLocal class. Each instance will be a database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Create a Base class. We will inherit from this class to create our models.
Base = declarative_base()


# Dependency to get the database session for each request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
