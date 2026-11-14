"""Hotkey parsing helpers (no Qt dependency).

Hotkeys are stored as human readable strings such as ``Alt+Space`` or
``Ctrl+Shift+K`` and converted to Win32 modifier flags plus a virtual-key code
when registered with ``RegisterHotKey``.
"""

from __future__ import annotations

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

MODIFIER_NAMES = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "super": MOD_WIN,
    "meta": MOD_WIN,
}

MODIFIER_LABELS = {
    MOD_ALT: "Alt",
    MOD_CONTROL: "Ctrl",
    MOD_SHIFT: "Shift",
    MOD_WIN: "Win",
}

#: Named keys mapped to Win32 virtual-key codes.
VK_NAMES = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "ins": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
    "num0": 0x60,
    "num1": 0x61,
    "num2": 0x62,
    "num3": 0x63,
    "num4": 0x64,
    "num5": 0x65,
    "num6": 0x66,
    "num7": 0x67,
    "num8": 0x68,
    "num9": 0x69,
    "multiply": 0x6A,
    "add": 0x6B,
    "subtract": 0x6D,
    "decimal": 0x6E,
    "divide": 0x6F,
    "semicolon": 0xBA,
    "plus": 0xBB,
    "comma": 0xBC,
    "minus": 0xBD,
    "period": 0xBE,
    "slash": 0xBF,
    "backtick": 0xC0,
    "grave": 0xC0,
    "lbracket": 0xDB,
    "rbracket": 0xDD,
    "backslash": 0xDC,
    "quote": 0xDE,
}

VK_LABELS = {
    0x20: "Space",
    0x1B: "Escape",
    0x0D: "Enter",
    0x09: "Tab",
    0x26: "Up",
    0x28: "Down",
    0x25: "Left",
    0x27: "Right",
    0x21: "PageUp",
    0x22: "PageDown",
    0x24: "Home",
    0x23: "End",
    0x2D: "Insert",
    0x2E: "Delete",
    0xBA: ";",
    0xBB: "+",
    0xBC: ",",
    0xBD: "-",
    0xBE: ".",
    0xBF: "/",
    0xC0: "`",
    0xDB: "[",
    0xDD: "]",
    0xDC: "\\",
    0xDE: "'",
}


class HotkeyError(ValueError):
    """Raised when a hotkey string cannot be parsed."""


def _key_to_vk(token: str) -> int:
    lower = token.lower()
    if lower in VK_NAMES:
        return VK_NAMES[lower]
    if len(token) == 1 and token.isalnum():
        return ord(token.upper())
    if lower.startswith("f") and lower[1:].isdigit() and 1 <= int(lower[1:]) <= 24:
        return 0x70 + int(lower[1:]) - 1
    if lower.isdigit():  # single digit handled above; multi-digit is invalid
        raise HotkeyError(f"Unknown key: {token}")
    raise HotkeyError(f"Unknown key: {token}")


def parse_hotkey(text: str) -> tuple[int, int]:
    """Parse ``"Alt+Space"`` into ``(modifiers, virtual_key)``.

    At least one modifier and exactly one non-modifier key are required.
    """
    if not text or not str(text).strip():
        raise HotkeyError("Hotkey is empty")

    tokens = [part.strip() for part in str(text).replace(" ", "").split("+")]
    tokens = [token for token in tokens if token]
    if not tokens:
        raise HotkeyError("Hotkey is empty")

    modifiers = 0
    keys: list[str] = []
    for token in tokens:
        modifier = MODIFIER_NAMES.get(token.lower())
        if modifier is not None:
            modifiers |= modifier
        else:
            keys.append(token)

    if not modifiers:
        raise HotkeyError("A hotkey needs at least one modifier (Ctrl, Alt, Shift or Win)")
    if len(keys) != 1:
        raise HotkeyError("A hotkey needs exactly one key")
    return modifiers, _key_to_vk(keys[0])


def format_hotkey(modifiers: int, vk: int) -> str:
    """Build a canonical hotkey string from modifier flags and a virtual key."""
    parts = [
        label
        for flag, label in ((MOD_CONTROL, "Ctrl"), (MOD_ALT, "Alt"), (MOD_SHIFT, "Shift"), (MOD_WIN, "Win"))
        if modifiers & flag
    ]
    if 0x41 <= vk <= 0x5A:
        parts.append(chr(vk))
    elif 0x30 <= vk <= 0x39:
        parts.append(chr(vk))
    elif 0x70 <= vk <= 0x87:
        parts.append(f"F{vk - 0x70 + 1}")
    else:
        parts.append(VK_LABELS.get(vk, f"0x{vk:02X}"))
    return "+".join(parts)


def normalize_hotkey(text: str) -> str:
    """Return the canonical form of *text* or raise :class:`HotkeyError`."""
    return format_hotkey(*parse_hotkey(text))


def is_valid_hotkey(text: str) -> bool:
    try:
        parse_hotkey(text)
        return True
    except HotkeyError:
        return False


__all__ = [
    "HotkeyError",
    "parse_hotkey",
    "format_hotkey",
    "normalize_hotkey",
    "is_valid_hotkey",
    "MOD_ALT",
    "MOD_CONTROL",
    "MOD_SHIFT",
    "MOD_WIN",
    "MOD_NOREPEAT",
]
