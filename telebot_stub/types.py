# Stub telebot.types so modules can be imported and tested without pyTelegramBotAPI installed.
# These stubs exist soley to make the import succeed; callers that build keyboards must still
# tolerate InlineKeyboardMarkup being None (the guard value) when the real library is absent.
InlineKeyboardMarkup = None
InlineKeyboardButton = None
ForceReply = None
ReplyKeyboardMarkup = None
KeyboardButton = None
ReplyKeyboardRemove = None
MenuButtonDefault = None
WebAppInfo = None
BotCommand = None
