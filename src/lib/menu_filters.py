from telegram.ext import filters

FILTER_GET_REPORT = filters.Regex(r"^📈")
FILTER_SETTINGS = filters.Regex(r"^⚙️")
FILTER_HELP = filters.Regex(r"^❓")
