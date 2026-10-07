from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    from sqlalchemy import Integer, String
    from sqlalchemy.orm import Mapped, mapped_column

    customer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Order(Base):
    __tablename__ = "orders"

    from sqlalchemy import Float, ForeignKey, Integer
    from sqlalchemy.orm import Mapped, mapped_column

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cust_id: Mapped[int] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)


class LineItem(Base):
    __tablename__ = "line_items"

    from sqlalchemy import Float, ForeignKey, Integer
    from sqlalchemy.orm import Mapped, mapped_column

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or settings.sqlalchemy_url, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def seed_sqlite(engine: Engine) -> None:
    """Create deterministic local data for tests and offline evaluation."""
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.query(Customer).first() is not None:
            return
        regions = ["New York", "California", "Texas", "Florida", "Washington"]
        session.add_all(
            Customer(
                customer_id=customer_id,
                name=f"Customer {customer_id}",
                region=None if customer_id % 11 == 0 else regions[(customer_id - 1) % len(regions)],
            )
            for customer_id in range(1, 151)
        )
        session.flush()
        session.add_all(
            Order(
                id=order_id,
                cust_id=((order_id - 1) % 150) + 1,
                total_amount=float(25 + (order_id * 17) % 975),
            )
            for order_id in range(1, 751)
        )
        session.flush()
        session.add_all(
            LineItem(
                id=item_id,
                order_id=((item_id - 1) % 750) + 1,
                qty=(item_id % 5) + 1,
                unit_price=float(5 + (item_id * 3) % 95),
            )
            for item_id in range(1, 1501)
        )
        session.commit()