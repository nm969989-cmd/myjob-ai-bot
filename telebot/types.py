# Stub telebot.types symbols used across the project.
# When pyTelegramBotAPI is installed, this file is shadowed by the real one
# in site-packages and never reached. When it is absent, these stubs let
# imports succeed and provide a minimal InlineKeyboardMarkup so that modules
# can be loaded and their keyboard-building functions can be called without
# crashing (e.g. during tests or in a dev sandbox without the Telegram lib).
#
# Production behaviour is UNCHANGED when pyTelegramBotAPI is installed: the
# real telebot.types is used everywhere, and these stubs are never imported.

from typing import Any, Dict, List, Optional


class _StubButton:
    """Minimal stand-in for telebot.types.InlineKeyboardButton.

    Implements the attributes the codebase and its tests read:
      - text, callback_data, url
      - to_dict() -> dict with 'text' and (when set) 'callback_data'/'url'
    """
    def __init__(self, text: str = "", url: Optional[str] = None,
                 callback_data: Optional[str] = None, **_unused: Any) -> None:
        self.text = text
        self.url = url
        self.callback_data = callback_data

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"text": self.text}
        if self.url is not None:
            d["url"] = self.url
        if self.callback_data is not None:
            d["callback_data"] = self.callback_data
        return d


class _StubMarkup:
    """Minimal stand-in for telebot.types.InlineKeyboardMarkup.

    Supports .row(*buttons) and .to_dict() so that:
      - tests calling markup.to_dict()['inline_keyboard'] work, where each
        row is a list of BUTTON DICTS (matching the real telebot contract), and
      - callers that iterate rows/buttons and read callback_data work.
    """
    def __init__(self) -> None:
        self._rows: List[List[_StubButton]] = []

    @property
    def keyboard(self) -> List[List[_StubButton]]:
        """Expose the rows list (mirrors real telebot's InlineKeyboardMarkup.keyboard)."""
        return self._rows

    def row(self, *buttons: _StubButton) -> None:
        self._rows.append(list(buttons))

    def to_dict(self) -> Dict[str, Any]:
        # Return the REAL telebot shape: list of rows, each row a list of
        # button DICTS (not button objects). Matches what the tests expect.
        return {
            "inline_keyboard": [
                [b.to_dict() for b in row]
                for row in self._rows
            ]
        }


# Public symbols used across the project.
InlineKeyboardMarkup = _StubMarkup
InlineKeyboardButton = _StubButton

# Remaining symbols used in import sites; None is safe here because callers
# that use these are guarded by the real library being present in production.
ForceReply = None
ReplyKeyboardMarkup = None
KeyboardButton = None
ReplyKeyboardRemove = None
MenuButtonDefault = None
WebAppInfo = None
BotCommand = None
