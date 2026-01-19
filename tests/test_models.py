from sqlalchemy import select

from src.database.models import User


class TestUserModel:
    def test_create_user(self, session):
        user = User(
            id=111111111,
            first_name="John",
            last_name="Doe",
            username="johndoe",
            language_code="en",
        )
        session.add(user)
        session.commit()

        stmt = select(User).where(User.id == 111111111)
        result = session.scalar(stmt)
        assert result is not None
        assert result.first_name == "John"
        assert result.username == "johndoe"

    def test_user_name_property(self, session):
        user = User(id=1, first_name="John", last_name="Doe")
        assert user.name == "John Doe"

        user2 = User(id=2, first_name="Jane", last_name=None)
        assert user2.name == "Jane"

    def test_selected_accounts_json(self, session):
        user = User(id=222222222, first_name="Test")
        user.selected_accounts = ["acc1", "acc2", "acc3"]
        session.add(user)
        session.commit()

        stmt = select(User).where(User.id == 222222222)
        result = session.scalar(stmt)
        assert result.selected_accounts == ["acc1", "acc2", "acc3"]

    def test_selected_accounts_empty(self, session):
        user = User(id=333333333, first_name="Test")
        session.add(user)
        session.commit()

        stmt = select(User).where(User.id == 333333333)
        result = session.scalar(stmt)
        assert result.selected_accounts == []

    def test_is_active_property(self, session):
        user = User(id=444444444, first_name="Test")
        session.add(user)
        session.commit()

        assert user.is_active is True

        user.deactivate()
        session.commit()
        assert user.is_active is False

        user.activate()
        session.commit()
        assert user.is_active is True

    def test_has_token_property(self, sample_user):
        assert sample_user.has_token is True

    def test_no_token(self, session):
        user = User(id=555555555, first_name="Test")
        session.add(user)
        session.commit()

        assert user.has_token is False

    def test_mention_url(self, sample_user):
        assert sample_user.mention_url == "tg://user?id=123456789"

    def test_mention_html(self, sample_user):
        mention = sample_user.mention
        assert "tg://user?id=123456789" in mention
        assert "Test User" in mention
