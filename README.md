# Monobank Daily Report Bot

Telegram bot that sends daily spending reports from your Monobank account.

## Features

- Multi-user support - each user adds their own Monobank token
- Customizable daily report time (per user)
- Spending breakdown by category (groceries, restaurants, transport, etc.)
- Manual report generation anytime
- Multiple account selection
- Ukrainian and English languages (switchable in settings)
- Encrypted token storage (per-user encryption)
- Monobank API rate limit handling (60 seconds between statement requests)

## Requirements

- Python 3.12+
- uv (package manager)
- Telegram Bot Token (from @BotFather)
- Monobank Personal API Token

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/monobankdaily.git
cd monobankdaily
```

2. Install dependencies with uv:

```bash
uv sync
```

3. Create `.env` file:

```bash
cp .env.example .env
```

4. Edit `.env` and add your Telegram bot token:

```
BOT_TOKEN=your_telegram_bot_token_here
DATABASE_URL=sqlite:///data/bot.db
TIMEZONE=Europe/Kiev
```

5. Run database migrations:

```bash
uv run alembic upgrade head
```

6. Compile translations:

```bash
make compile-translations
```

## Running

```bash
make run
```

Or directly:

```bash
uv run monobankdaily
```

## Usage

1. Start the bot with `/start` command
2. Go to Settings and add your Monobank token:
   - Open Monobank app
   - Go to Settings -> API
   - Create a personal token
   - Send token to the bot
3. Select accounts to track
4. Set your preferred report time (default: 21:00 Kyiv time)
5. Optionally change language (Ukrainian/English)
6. Wait for daily report or use "Get Report Now" button

## Development

### Running tests

```bash
make test
```

### Linting

```bash
make lint
```

### Format code

```bash
make format
```

## Security

- Monobank tokens are encrypted using Fernet symmetric encryption
- Each user token is encrypted with a key derived from their Telegram user ID
- Master encryption key is stored in `data/.secret_key` (auto-generated)
- Never commit `.env` or `data/` folder to version control

## API Rate Limits

The bot respects Monobank API rate limits:
- Statement endpoint: 1 request per 60 seconds per token
- Client info endpoint: no documented limit

When fetching multiple accounts, the bot automatically waits between requests.

## License

MIT
