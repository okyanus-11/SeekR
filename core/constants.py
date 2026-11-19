"""Constants shared by the core, feature and UI layers."""

from __future__ import annotations

THEME_IDS = ("dark", "light", "amoled", "catppuccin_mocha", "dracula", "nord")

THEME_LABELS = {
    "dark": "Graphite",
    "light": "Light",
    "amoled": "AMOLED",
    "catppuccin_mocha": "Catppuccin Mocha",
    "dracula": "Dracula",
    "nord": "Nord",
}

#: Keyword -> human readable description. Documented in the README as well.
KEYWORDS = {
    ">": "Open the unified command center",
    "web": "Search the web",
    "calc": "Calculate an expression",
    "comm": "Run a command",
    "file": "Search indexed files and folders",
    "content": "Search inside configured indexed text files",
    "app": "Search installed applications",
    "wiki": "Search Wikipedia",
    "yt": "Search YouTube",
    "gh": "Search GitHub repositories",
    "translate": "Translate text",
    "unit": "Convert units",
    "time": "Look up or convert time zones",
    "define": "Look up a word definition",
    "sys": "Show live system information",
    # Extended keywords (documented as additional SeekR keywords)
    "note": "Search quick notes",
    "clip": "Search clipboard history",
    "win": "Switch between open windows",
    "ps": "Search running processes",
    "emoji": "Search and copy emoji",
    "color": "Pick a color",
    "shot": "Take a screenshot",
    "bm": "Search browser bookmarks",
    "ssh": "Open a saved SSH profile",
    "act": "Run a quick action",
    "flow": "Search and run saved workflows",
    "snip": "Search and copy text snippets",
    "chain": "Run a sequence of existing commands",
    "wm": "Manage open application windows",
}

#: Keywords providers claim at runtime; kept here so settings can list them.
PRIMARY_KEYWORDS = ("web", "calc", "comm", "file", "app", "wiki", "yt", "gh", "translate", "unit", "time", "define", "sys")

#: URL templates use ``{query}`` which is always percent-encoded.
WEB_ENGINES = {
    "duckduckgo": {
        "label": "DuckDuckGo",
        "url": "https://duckduckgo.com/?q={query}",
    },
    "google": {
        "label": "Google",
        "url": "https://www.google.com/search?q={query}",
    },
    "bing": {
        "label": "Bing",
        "url": "https://www.bing.com/search?q={query}",
    },
    "youtube": {
        "label": "YouTube",
        "url": "https://www.youtube.com/results?search_query={query}",
    },
    "wikipedia": {
        "label": "Wikipedia",
        "url": "https://en.wikipedia.org/w/index.php?search={query}",
    },
    "github": {
        "label": "GitHub",
        "url": "https://github.com/search?q={query}&type=repositories",
    },
    "stackoverflow": {
        "label": "Stack Overflow",
        "url": "https://stackoverflow.com/search?q={query}",
    },
    "translate": {
        "label": "Google Translate",
        "url": "https://translate.google.com/?sl=auto&tl=tr&text={query}",
    },
}

WEB_ENGINE_LABELS = {key: value["label"] for key, value in WEB_ENGINES.items()}

CATEGORIES = (
    "Application",
    "File",
    "File content",
    "Folder",
    "Calculator",
    "Web",
    "Command",
    "Clipboard",
    "Note",
    "System",
    "Developer",
    "Date & Time",
    "Window",
    "Process",
    "Emoji",
    "Color",
    "Screenshot",
    "Bookmark",
    "Connection",
    "Action",
    "Workflow",
    "Snippet",
    "Window management",
    "Command chain",
    "Keyword",
)

#: Directories never indexed by the file indexer.
DEFAULT_EXCLUDED_DIRS = (
    "node_modules",
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "AppData",
    "$Recycle.Bin",
    "System Volume Information",
    "Windows",
    "Program Files",
    "Program Files (x86)",
    ".cache",
    ".npm",
    ".gradle",
    ".m2",
)

DEFAULT_EXCLUDED_EXTENSIONS = (
    ".tmp",
    ".temp",
    ".log",
    ".bak",
    ".dll",
    ".sys",
    ".drv",
    ".pdb",
    ".lnk",
    ".db-wal",
    ".db-shm",
    ".pyc",
)

DATE_FORMAT_PRESETS = (
    "%Y-%m-%d %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%m/%d/%Y %I:%M %p",
    "%Y-%m-%d",
    "%H:%M:%S",
    "%A, %d %B %Y %H:%M",
)

__all__ = [
    "THEME_IDS",
    "THEME_LABELS",
    "KEYWORDS",
    "PRIMARY_KEYWORDS",
    "WEB_ENGINES",
    "WEB_ENGINE_LABELS",
    "CATEGORIES",
    "DEFAULT_EXCLUDED_DIRS",
    "DEFAULT_EXCLUDED_EXTENSIONS",
    "DATE_FORMAT_PRESETS",
]
