"""Emoji search."""

from __future__ import annotations

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

# (emoji, name, extra keywords)
EMOJI: tuple[tuple[str, str, str], ...] = (
    ("😀", "grinning face", "smile happy joy"),
    ("😃", "smiling face", "happy smile"),
    ("😄", "grinning face smiling eyes", "happy laugh"),
    ("😁", "beaming face", "grin happy"),
    ("😆", "laughing", "lol happy"),
    ("😅", "sweat smile", "relief nervous"),
    ("😂", "face with tears of joy", "lol funny cry"),
    ("🤣", "rolling on the floor laughing", "lol rofl"),
    ("😊", "smiling face with smiling eyes", "happy blush"),
    ("😇", "smiling face with halo", "angel innocent"),
    ("🙂", "slightly smiling face", "smile"),
    ("🙃", "upside down face", "silly irony"),
    ("😉", "winking face", "wink"),
    ("😌", "relieved face", "calm peace"),
    ("😍", "smiling face with heart eyes", "love crush"),
    ("🥰", "smiling face with hearts", "love adore"),
    ("😘", "face blowing a kiss", "kiss love"),
    ("😗", "kissing face", "kiss"),
    ("😙", "kissing face smiling eyes", "kiss"),
    ("😚", "kissing face closed eyes", "kiss"),
    ("😋", "face savoring food", "yummy tasty"),
    ("😛", "face with tongue", "silly"),
    ("😜", "winking face with tongue", "joke silly"),
    ("🤪", "zany face", "crazy wild"),
    ("😝", "squinting face with tongue", "silly"),
    ("🤑", "money mouth face", "rich money"),
    ("🤗", "hugging face", "hug welcome"),
    ("🤭", "face with hand over mouth", "oops giggle"),
    ("🤫", "shushing face", "quiet secret"),
    ("🤔", "thinking face", "hmm question"),
    ("🤐", "zipper mouth face", "secret silence"),
    ("🤨", "raised eyebrow", "skeptical doubt"),
    ("😐", "neutral face", "meh"),
    ("😑", "expressionless face", "blank"),
    ("😶", "face without mouth", "silent"),
    ("😏", "smirking face", "smug"),
    ("😒", "unamused face", "annoyed"),
    ("🙄", "face with rolling eyes", "whatever"),
    ("😬", "grimacing face", "awkward"),
    ("🤥", "lying face", "lie"),
    ("😔", "pensive face", "sad thoughtful"),
    ("😪", "sleepy face", "tired"),
    ("🤤", "drooling face", "hungry"),
    ("😴", "sleeping face", "sleep zzz"),
    ("😷", "face with medical mask", "sick"),
    ("🤒", "face with thermometer", "sick fever"),
    ("🤕", "face with head bandage", "hurt"),
    ("🤢", "nauseated face", "sick gross"),
    ("🤮", "vomiting face", "sick"),
    ("🥵", "hot face", "heat"),
    ("🥶", "cold face", "freezing"),
    ("🥴", "woozy face", "drunk dizzy"),
    ("😵", "dizzy face", "dead knocked out"),
    ("🤯", "exploding head", "mind blown"),
    ("🤠", "cowboy hat face", "yeehaw"),
    ("🥳", "partying face", "party celebrate"),
    ("😎", "smiling face with sunglasses", "cool"),
    ("🤓", "nerd face", "geek glasses"),
    ("🧐", "face with monocle", "inspect"),
    ("😕", "confused face", "unsure"),
    ("😟", "worried face", "anxious"),
    ("🙁", "slightly frowning face", "sad"),
    ("😮", "face with open mouth", "surprised wow"),
    ("😯", "hushed face", "surprise"),
    ("😲", "astonished face", "shock"),
    ("😳", "flushed face", "embarrassed"),
    ("🥺", "pleading face", "please puppy"),
    ("😦", "frowning face with open mouth", "worried"),
    ("😨", "fearful face", "scared"),
    ("😰", "anxious face with sweat", "stress"),
    ("😥", "sad but relieved face", "phew"),
    ("😢", "crying face", "sad tear"),
    ("😭", "loudly crying face", "sob sad"),
    ("😱", "face screaming in fear", "shock scream"),
    ("😖", "confounded face", "frustrated"),
    ("😣", "persevering face", "struggle"),
    ("😞", "disappointed face", "sad"),
    ("😓", "downcast face with sweat", "tired"),
    ("😩", "weary face", "tired exhausted"),
    ("😫", "tired face", "exhausted"),
    ("🥱", "yawning face", "bored tired"),
    ("😤", "face with steam from nose", "angry triumph"),
    ("😡", "pouting face", "angry mad"),
    ("😠", "angry face", "mad"),
    ("🤬", "face with symbols on mouth", "swearing angry"),
    ("😈", "smiling face with horns", "devil"),
    ("👿", "angry face with horns", "devil"),
    ("💀", "skull", "dead death"),
    ("💩", "pile of poo", "poop"),
    ("🤡", "clown face", "clown"),
    ("👻", "ghost", "halloween"),
    ("👽", "alien", "ufo space"),
    ("🤖", "robot", "bot ai"),
    ("😺", "grinning cat", "cat"),
    ("😸", "grinning cat smiling eyes", "cat"),
    ("😹", "cat with tears of joy", "cat laugh"),
    ("😻", "smiling cat heart eyes", "cat love"),
    ("🙀", "weary cat", "cat shock"),
    ("😿", "crying cat", "cat sad"),
    ("😾", "pouting cat", "cat angry"),
    ("🙈", "see no evil monkey", "monkey"),
    ("🙉", "hear no evil monkey", "monkey"),
    ("🙊", "speak no evil monkey", "monkey"),
    ("❤️", "red heart", "love"),
    ("🧡", "orange heart", "love"),
    ("💛", "yellow heart", "love"),
    ("💚", "green heart", "love"),
    ("💙", "blue heart", "love"),
    ("💜", "purple heart", "love"),
    ("🖤", "black heart", "love dark"),
    ("🤍", "white heart", "love"),
    ("💔", "broken heart", "sad love"),
    ("💯", "hundred points", "perfect score"),
    ("🔥", "fire", "hot lit"),
    ("✨", "sparkles", "magic shine"),
    ("🎉", "party popper", "celebrate"),
    ("🎊", "confetti ball", "celebrate"),
    ("👍", "thumbs up", "like yes ok"),
    ("👎", "thumbs down", "dislike no"),
    ("👏", "clapping hands", "applause"),
    ("🙌", "raising hands", "celebrate"),
    ("🤝", "handshake", "deal agree"),
    ("🙏", "folded hands", "please thanks pray"),
    ("✌️", "victory hand", "peace"),
    ("🤞", "crossed fingers", "luck hope"),
    ("👌", "ok hand", "perfect"),
    ("🫡", "saluting face", "salute"),
    ("💪", "flexed biceps", "strong muscle"),
    ("🧠", "brain", "smart think"),
    ("👀", "eyes", "look watch"),
    ("💡", "light bulb", "idea"),
    ("✅", "check mark", "done yes"),
    ("❌", "cross mark", "no wrong"),
    ("⚠️", "warning", "alert caution"),
    ("🚀", "rocket", "launch fast space"),
    ("🎯", "bullseye", "target goal"),
    ("📌", "pushpin", "pin important"),
    ("📎", "paperclip", "attach"),
    ("📁", "folder", "files"),
    ("📄", "page", "document file"),
    ("📝", "memo", "note write"),
    ("📅", "calendar", "date"),
    ("⏰", "alarm clock", "time wake"),
    ("⌛", "hourglass", "wait time"),
    ("🔍", "magnifying glass", "search find"),
    ("🔒", "locked", "lock secure"),
    ("🔑", "key", "password access"),
    ("🛠️", "hammer and wrench", "tools fix"),
    ("⚙️", "gear", "settings config"),
    ("💻", "laptop", "computer developer"),
    ("🖥️", "desktop computer", "computer"),
    ("⌨️", "keyboard", "typing input"),
    ("🖱️", "computer mouse", "click"),
    ("📱", "mobile phone", "phone"),
    ("🔋", "battery", "power charge"),
    ("🌐", "globe with meridians", "web internet world"),
    ("☁️", "cloud", "weather cloud"),
    ("🌙", "crescent moon", "night dark"),
    ("☀️", "sun", "day light"),
    ("⭐", "star", "favourite"),
    ("🎵", "musical note", "music"),
    ("🎮", "video game", "gaming"),
    ("📷", "camera", "photo"),
    ("💾", "floppy disk", "save"),
    ("📦", "package", "box shipping"),
    ("💰", "money bag", "money"),
    ("🏆", "trophy", "win award"),
    ("🎓", "graduation cap", "education"),
    ("🍕", "pizza", "food"),
    ("☕", "hot beverage", "coffee tea"),
    ("🍺", "beer mug", "drink"),
    ("🌍", "earth globe europe africa", "world"),
    ("🐍", "snake", "python"),
    ("🐧", "penguin", "linux"),
    ("🦀", "crab", "rust"),
    ("🐳", "whale", "docker"),
    ("⚡", "high voltage", "fast power"),
    ("♻️", "recycling symbol", "recycle"),
    ("❓", "question mark", "help"),
    ("❗", "exclamation mark", "important"),
    ("🔔", "bell", "notification"),
    ("🎁", "wrapped gift", "present"),
)


def search_emojis(query: str, limit: int = 20) -> list[tuple[str, str]]:
    text = (query or "").strip()
    if not text:
        return [(emoji, name) for emoji, name, _ in EMOJI[:limit]]
    scored: list[tuple[float, str, str]] = []
    lowered = text.lower()
    for emoji, name, keywords in EMOJI:
        haystack = f"{name} {keywords}"
        if lowered in haystack:
            score = 1.0 if name.startswith(lowered) else 0.9
        else:
            score = fuzzy_score(text, name, typo_tolerance=True)
            if score <= 0:
                score = fuzzy_score(text, keywords, typo_tolerance=False) * 0.7
        if score > 0:
            scored.append((score, emoji, name))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [(emoji, name) for _, emoji, name in scored[:limit]]


class EmojiProvider(SearchProvider):
    """The ``emoji`` keyword."""

    id = "emoji"
    title = "Emoji"
    keyword = "emoji"
    weight = 0.8
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        results = search_emojis(query, limit)
        if not results and query.strip():
            return [
                self.make_result(
                    title=f"No emoji matches “{query.strip()}”",
                    subtitle="Try a different keyword, for example: fire, heart, check",
                    category="Emoji",
                    score=0.7,
                    icon_glyph="🙂",
                )
            ]
        return [
            self.make_result(
                title=f"{emoji}  {name.title()}",
                subtitle=f"Enter copies {emoji}",
                category="Emoji",
                score=0.9 - index * 0.01,
                primary=lambda e=emoji: self._copy(e),
                actions=[ResultAction("Copy emoji", lambda e=emoji: self.hooks.copy_text(e))],
                copy_text=emoji,
                icon_glyph=emoji,
            )
            for index, (emoji, name) in enumerate(results)
        ]

    def _copy(self, emoji: str) -> None:
        self.hooks.copy_text(emoji)
        self.hooks.notify(f"Copied {emoji}")
        self.hooks.hide_launcher()


__all__ = ["EMOJI", "search_emojis", "EmojiProvider"]
