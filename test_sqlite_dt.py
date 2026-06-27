import datetime
from sqlalchemy import create_engine, Column, Integer, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class TestModel(Base):
    __tablename__ = 'test_table'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

engine = create_engine('sqlite:///:memory:', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Insert aware datetime
obj1 = TestModel()
session.add(obj1)
session.commit()

# query raw sqlite
with engine.connect() as conn:
    from sqlalchemy import text
    res = conn.execute(text("SELECT timestamp FROM test_table")).fetchall()
    print("Stored in SQLite:", res[0][0])
