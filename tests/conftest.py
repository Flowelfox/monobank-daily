from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, User


@pytest.fixture
def tmp_secret_key(tmp_path):
    secret_file = tmp_path / ".secret_key"
    with patch("src.lib.crypto.SECRET_KEY_FILE", secret_file):
        yield secret_file


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_user(session, tmp_secret_key):
    user = User(
        id=123456789,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="uk",
    )
    user.monobank_token = "uTestToken123456789012345678901234567890"
    user.selected_accounts = ["account1", "account2"]
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def sample_transactions():
    return [
        {
            "id": "tx1",
            "time": 1705660800,
            "description": "Grocery Store",
            "mcc": 5411,
            "amount": -15000,
            "balance": 100000,
        },
        {
            "id": "tx2",
            "time": 1705661000,
            "description": "Restaurant",
            "mcc": 5812,
            "amount": -25000,
            "balance": 75000,
        },
        {
            "id": "tx3",
            "time": 1705661200,
            "description": "Salary",
            "mcc": 6011,
            "amount": 500000,
            "balance": 575000,
        },
        {
            "id": "tx4",
            "time": 1705661400,
            "description": "Gas Station",
            "mcc": 5541,
            "amount": -30000,
            "balance": 545000,
        },
    ]


@pytest.fixture
def sample_accounts():
    return [
        {
            "id": "account1",
            "type": "black",
            "currencyCode": 980,
            "maskedPan": ["537541******1234"],
            "balance": 100000,
        },
        {
            "id": "account2",
            "type": "white",
            "currencyCode": 980,
            "maskedPan": ["537541******5678"],
            "balance": 50000,
        },
        {
            "id": "account3",
            "type": "fop",
            "currencyCode": 980,
            "maskedPan": [],
            "balance": 200000,
        },
    ]
