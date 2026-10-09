# Local stub package so that 'from telebot.types import ...' resolves when
# pyTelegramBotAPI is NOT installed (e.g. in a dev sandbox or during tests).
#
# IMPORTANT: in production the real pyTelegramBotAPI package on site-packages
# is found by Python's import system BEFORE this local dir when the real
# package is installed, because site-packages PathFinder entries come after
# the script's directory only when no matching package exists there. When
# pyTelegramBotAPI IS installed, the real 'telebot' package lives in
# site-packages and is imported; this stub is then a harmless no-op that is
# never reached. When pyTelegramBotAPI is ABSENT, this stub is what gets
# imported, so imports do not crash.
#
# The real 'telebot' package would normally provide more than types, but
# every import site in this codebase only ever imports from telebot.types
# (InlineKeyboardMarkup, InlineKeyboardButton, etc.) or telebot itself
# (TeleBot). The stubs below cover the telebot.types symbols used here.
