import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

MONOBANK_API_URL = "https://api.monobank.ua"

STATEMENT_RATE_LIMIT_SECONDS = 60
_last_statement_request: dict[str, float] = {}

MCC_CATEGORIES = {
    "groceries": {
        "name_uk": "🛒 Продукти",
        "name_en": "🛒 Groceries",
        "codes": [5411, 5412, 5422, 5441, 5451, 5462, 5499],
    },
    "restaurants": {
        "name_uk": "🍔 Ресторани та кафе",
        "name_en": "🍔 Restaurants & Cafes",
        "codes": [5812, 5813, 5814],
    },
    "transport": {
        "name_uk": "🚗 Транспорт",
        "name_en": "🚗 Transport",
        "codes": [4111, 4112, 4121, 4131, 4411, 4511, 4784, 5541, 5542, 5172, 7512, 7523],
    },
    "entertainment": {
        "name_uk": "🎬 Розваги",
        "name_en": "🎬 Entertainment",
        "codes": [7832, 7841, 7911, 7922, 7929, 7932, 7933, 7941, 7991, 7992, 7993, 7994, 7995, 7996, 7997, 7998, 7999],
    },
    "health": {
        "name_uk": "💊 Здоров'я",
        "name_en": "💊 Health",
        "codes": [5122, 5292, 5912, 5975, 5976, 5977, 8011, 8021, 8031, 8041, 8042, 8043, 8049, 8050, 8062, 8071, 8099],
    },
    "clothing": {
        "name_uk": "👕 Одяг та взуття",
        "name_en": "👕 Clothing & Shoes",
        "codes": [5611, 5621, 5631, 5641, 5651, 5661, 5681, 5691, 5699, 5931, 5932, 5948],
    },
    "utilities": {
        "name_uk": "🏠 Комунальні послуги",
        "name_en": "🏠 Utilities",
        "codes": [4814, 4816, 4821, 4899, 4900],
    },
    "electronics": {
        "name_uk": "📱 Електроніка",
        "name_en": "📱 Electronics",
        "codes": [5045, 5046, 5065, 5722, 5732, 5733, 5734, 5735],
    },
    "education": {
        "name_uk": "📚 Освіта",
        "name_en": "📚 Education",
        "codes": [5111, 5192, 5942, 5943, 5994, 8211, 8220, 8241, 8244, 8249, 8299],
    },
    "transfers": {
        "name_uk": "💸 Перекази",
        "name_en": "💸 Transfers",
        "codes": [4829, 6010, 6011, 6012, 6051, 6211, 6300, 6540],
    },
    "other": {
        "name_uk": "📦 Інше",
        "name_en": "📦 Other",
        "codes": [],
    },
}


def get_category_for_mcc(mcc: int) -> str:
    for category_key, category_data in MCC_CATEGORIES.items():
        codes = category_data["codes"]
        if isinstance(codes, list) and mcc in codes:
            return category_key
    return "other"


def get_category_name(category_key: str, language: str = "uk") -> str:
    category = MCC_CATEGORIES.get(category_key, MCC_CATEGORIES["other"])
    name = category.get(f"name_{language}", category.get("name_en", "Other"))
    return str(name)


class MonobankAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, retry_after: int | None = None):
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(self.message)


class MonobankRateLimitError(MonobankAPIError):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            f"Rate limit exceeded. Retry after {retry_after} seconds.", status_code=429, retry_after=retry_after
        )


class MonobankService:
    def __init__(self, token: str):
        self.token = token
        self.headers = {"X-Token": token}

    async def get_client_info(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MONOBANK_API_URL}/personal/client-info", headers=self.headers)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise MonobankAPIError("Invalid token", status_code=401)
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise MonobankRateLimitError(retry_after=retry_after)
            else:
                raise MonobankAPIError(f"API error: {response.text}", status_code=response.status_code)

    async def get_statement(
        self, account: str, from_ts: int, to_ts: int | None = None, respect_rate_limit: bool = True
    ) -> list[dict]:
        if respect_rate_limit:
            await self._wait_for_rate_limit()

        url = f"{MONOBANK_API_URL}/personal/statement/{account}/{from_ts}"
        if to_ts:
            url += f"/{to_ts}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)

            _last_statement_request[self.token] = time.time()

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise MonobankAPIError("Invalid token", status_code=401)
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise MonobankRateLimitError(retry_after=retry_after)
            else:
                raise MonobankAPIError(f"API error: {response.text}", status_code=response.status_code)

    async def _wait_for_rate_limit(self):
        last_request = _last_statement_request.get(self.token, 0)
        elapsed = time.time() - last_request

        if elapsed < STATEMENT_RATE_LIMIT_SECONDS:
            wait_time = STATEMENT_RATE_LIMIT_SECONDS - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.1f} seconds before next statement request")
            await asyncio.sleep(wait_time)

    async def get_accounts(self) -> list[dict]:
        client_info = await self.get_client_info()
        return client_info.get("accounts", [])

    async def validate_token(self) -> bool:
        try:
            await self.get_client_info()
            return True
        except MonobankAPIError:
            return False


async def get_daily_spending(token: str, accounts: list[str], from_ts: int, to_ts: int, language: str = "uk") -> dict:
    service = MonobankService(token)

    all_transactions = []
    for account_id in accounts:
        try:
            transactions = await service.get_statement(account_id, from_ts, to_ts, respect_rate_limit=True)
            all_transactions.extend(transactions)
        except MonobankRateLimitError as e:
            retry_after = e.retry_after if e.retry_after is not None else 60
            logger.warning(f"Rate limit hit for account {account_id}, waiting {retry_after}s and retrying...")
            await asyncio.sleep(retry_after)
            try:
                transactions = await service.get_statement(account_id, from_ts, to_ts, respect_rate_limit=False)
                all_transactions.extend(transactions)
            except MonobankAPIError as retry_error:
                logger.warning(f"Failed to get statement for account {account_id} after retry: {retry_error}")
                continue
        except MonobankAPIError as e:
            logger.warning(f"Failed to get statement for account {account_id}: {e}")
            continue

    spending_by_category: dict[str, int] = {}
    total_spending = 0
    total_income = 0

    for tx in all_transactions:
        amount = tx.get("amount", 0)
        mcc = tx.get("mcc", 0)

        if amount < 0:
            category = get_category_for_mcc(mcc)
            spending_by_category[category] = spending_by_category.get(category, 0) + abs(amount)
            total_spending += abs(amount)
        else:
            total_income += amount

    categories_formatted = []
    for category_key, amount in sorted(spending_by_category.items(), key=lambda x: x[1], reverse=True):
        category_name = get_category_name(category_key, language)
        categories_formatted.append({"key": category_key, "name": category_name, "amount": amount})

    return {
        "total_spending": total_spending,
        "total_income": total_income,
        "categories": categories_formatted,
        "transaction_count": len(all_transactions),
    }


def format_account_name(account: dict) -> str:
    account_type = account.get("type", "")
    currency_code = account.get("currencyCode", 980)

    currency_symbols = {
        980: "₴",
        840: "$",
        978: "€",
    }
    currency = currency_symbols.get(currency_code, str(currency_code))

    masked_pan = account.get("maskedPan", [""])[0] if account.get("maskedPan") else ""
    if masked_pan:
        last_four = masked_pan[-4:] if len(masked_pan) >= 4 else masked_pan
    else:
        last_four = ""

    if account_type == "black":
        name = "💳 Чорна картка"
    elif account_type == "white":
        name = "💳 Біла картка"
    elif account_type == "platinum":
        name = "💎 Platinum"
    elif account_type == "iron":
        name = "🔩 Залізна картка"
    elif account_type == "fop":
        name = "💼 ФОП"
    elif account_type == "eAid":
        name = "🇺🇦 єПідтримка"
    else:
        name = f"💳 {account_type}"

    if last_four:
        name += f" *{last_four}"

    name += f" ({currency})"

    return name
