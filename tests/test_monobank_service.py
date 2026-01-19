from unittest.mock import AsyncMock, patch

import pytest

from src.services.monobank import (
    MonobankAPIError,
    MonobankService,
    format_account_name,
    get_category_for_mcc,
    get_category_name,
    get_daily_spending,
)


class TestMCCCategories:
    def test_groceries_mcc(self):
        assert get_category_for_mcc(5411) == "groceries"
        assert get_category_for_mcc(5412) == "groceries"

    def test_restaurants_mcc(self):
        assert get_category_for_mcc(5812) == "restaurants"
        assert get_category_for_mcc(5814) == "restaurants"

    def test_transport_mcc(self):
        assert get_category_for_mcc(5541) == "transport"
        assert get_category_for_mcc(4121) == "transport"

    def test_unknown_mcc(self):
        assert get_category_for_mcc(9999) == "other"
        assert get_category_for_mcc(0) == "other"

    def test_category_name_uk(self):
        assert "Продукти" in get_category_name("groceries", "uk")
        assert "Ресторани" in get_category_name("restaurants", "uk")

    def test_category_name_en(self):
        assert "Groceries" in get_category_name("groceries", "en")
        assert "Restaurants" in get_category_name("restaurants", "en")


class TestFormatAccountName:
    def test_black_card(self, sample_accounts):
        account = sample_accounts[0]
        name = format_account_name(account)
        assert "Чорна картка" in name
        assert "1234" in name
        assert "₴" in name

    def test_white_card(self, sample_accounts):
        account = sample_accounts[1]
        name = format_account_name(account)
        assert "Біла картка" in name
        assert "5678" in name

    def test_fop_account(self, sample_accounts):
        account = sample_accounts[2]
        name = format_account_name(account)
        assert "ФОП" in name

    def test_usd_account(self):
        account = {"id": "test", "type": "black", "currencyCode": 840, "maskedPan": ["1234"]}
        name = format_account_name(account)
        assert "$" in name


class TestMonobankService:
    @pytest.mark.asyncio
    async def test_validate_token_success(self):
        service = MonobankService("test_token")

        with patch.object(service, "get_client_info", new_callable=AsyncMock) as mock:
            mock.return_value = {"clientId": "test"}
            result = await service.validate_token()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_token_failure(self):
        service = MonobankService("invalid_token")

        with patch.object(service, "get_client_info", new_callable=AsyncMock) as mock:
            mock.side_effect = MonobankAPIError("Invalid token", 401)
            result = await service.validate_token()
            assert result is False

    @pytest.mark.asyncio
    async def test_get_accounts(self):
        service = MonobankService("test_token")

        with patch.object(service, "get_client_info", new_callable=AsyncMock) as mock:
            mock.return_value = {"clientId": "test", "accounts": [{"id": "acc1"}, {"id": "acc2"}]}
            accounts = await service.get_accounts()
            assert len(accounts) == 2
            assert accounts[0]["id"] == "acc1"


class TestGetDailySpending:
    @pytest.mark.asyncio
    async def test_daily_spending_calculation(self, sample_transactions):
        with patch("src.services.monobank.MonobankService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_statement = AsyncMock(return_value=sample_transactions)

            result = await get_daily_spending("token", ["account1"], 1705660000, 1705670000, "uk")

            assert result["total_spending"] == 70000
            assert result["total_income"] == 500000
            assert result["transaction_count"] == 4

            categories = {c["key"]: c["amount"] for c in result["categories"]}
            assert categories["groceries"] == 15000
            assert categories["restaurants"] == 25000
            assert categories["transport"] == 30000

    @pytest.mark.asyncio
    async def test_empty_transactions(self):
        with patch("src.services.monobank.MonobankService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_statement = AsyncMock(return_value=[])

            result = await get_daily_spending("token", ["account1"], 1705660000, 1705670000, "uk")

            assert result["total_spending"] == 0
            assert result["total_income"] == 0
            assert result["transaction_count"] == 0
            assert result["categories"] == []

    @pytest.mark.asyncio
    async def test_multiple_accounts(self, sample_transactions):
        with patch("src.services.monobank.MonobankService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_statement = AsyncMock(return_value=sample_transactions[:2])

            await get_daily_spending("token", ["account1", "account2"], 1705660000, 1705670000, "uk")

            assert mock_instance.get_statement.call_count == 2
