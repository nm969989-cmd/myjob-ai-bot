# Local stub so 'from telebot.types import ...' resolves when pyTelegramBotAPI is absent.
# In production (bot running with telebot installed) the real telebot package on site-packages
# is found first via sys.path order, so this stub is a no-op.
