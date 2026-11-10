"""The three emojis that stand in for a room number (which the site never shows).

A listing's emojis are any three emojis except flags, generated or typed in. Two listings
can't have the same three, in any order. They are a label for people, never a key.
"""

from __future__ import annotations
import secrets
from typing import Optional

# Friendly, unambiguous, single-codepoint emojis for the "roll" button. Typed-in emojis are
# not limited to this list.
POOL = list(
    "🐶🐱🐭🐹🐰🦊🐻🐼🐨🐯🦁🐮🐷🐸🐵🐔🐧🐦🐤🦆🦉🦇🐺🐗🐴🦄🐝🐛🦋🐌🐞🐜🐢🐍🦎🐙🦑🦐🦀🐡🐠🐟🐬🐳🐋🦈🐊🐅🐆🦓🦍🐘🦏🐪🐫🦒🐃🐂🐄🐎🐖🐏🐑🐐🦌🐕🐩🐈🐓🦃🐇🐁🐀🦔"
    "🌵🎄🌲🌳🌴🌱🌿🍀🎍🎋🍃🍂🍁🍄🌾💐🌷🌹🌺🌸🌼🌻🌞🌝🌛🌜🌚🌙🌎⭐🌟✨⚡🔥🌈☔⛄🌊"
    "🍏🍎🍐🍊🍋🍌🍉🍇🍓🍈🍒🍑🍍🥝🥑🍅🍆🥒🥕🌽🥔🍠🌰🥜🍯🥐🍞🥖🧀🥚🍳🥞🍤🍗🍖🍕🌭🍔🍟🥙🌮🌯🥗🍝🍜🍲🍥🍣🍱🍛🍙🍚🍘🍢🍡🍧🍨🍦🍰🎂🍮🍭🍬🍫🍿🍩🍪🥛🍵🍶🍺🥤"
    "⚽🏀🏈⚾🎾🏐🏉🎱🏓🏸🥅🏒🏑🏏⛳🏹🎣🥊🥋⛸🎿🎯🎮🎲🎨🎬🎤🎧🎼🎹🥁🎷🎺🎸🎻🎪🎭🎳"
    "🚗🚕🚙🚌🚎🏎🚓🚑🚒🚐🚚🚛🚜🛴🚲🛵🚂🚆🚇🚊🚀🛸🚁⛵🚤🛶⚓🗿🗽🏰🏯🎡🎢🎠⛲🏝🌋🗻🏕⛺🏠🏡"
    "⌚📱💻🖨🕹💽💾💿📷📹🎥📞📺📻🧭⏰⌛📡🔋🔌💡🔦🕯💎🔧🔨🔩🧲🔮🔭🔬💊🧬🧪🧹🧺🧻🧼🧽🚪🛏🛋🚽🚿🛁🔑🧸🎁🎈🎀🎊🎉🏮📦📫📜📚📖🔖📎📌✂📝🔍🔒"
)
# No duplicates, and nothing that most phones draw as a black-and-white symbol.
POOL = [e for e in dict.fromkeys(POOL) if e not in "🏎🖨🕹🕯⛸🏝🏕🛏🛋✂"]

_VS16, _ZWJ, _KEYCAP = 0xFE0F, 0x200D, 0x20E3
_FLAG_BASES = {0x1F3C1, 0x1F6A9, 0x1F38C, 0x1F3F4, 0x1F3F3}  # 🏁 🚩 🎌 🏴 🏳 (and their sequences)


def _is_emoji_base(cp: int) -> bool:
    return (0x1F300 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF or 0x2300 <= cp <= 0x23FF
            or 0x2B00 <= cp <= 0x2BFF or 0x2190 <= cp <= 0x21FF or 0x25AA <= cp <= 0x25FE
            or cp in (0xA9, 0xAE, 0x203C, 0x2049, 0x2122, 0x2139, 0x24C2, 0x2934, 0x2935, 0x3030, 0x303D, 0x3297, 0x3299))


def split(text: str) -> Optional[list[str]]:
    """Split a string into emojis (one per visible symbol). None if anything in it is not an
    emoji, or is a flag."""
    cps = [ord(ch) for ch in text if not ch.isspace()]
    out: list[str] = []
    i = 0
    while i < len(cps):
        cp = cps[i]
        if 0x1F1E6 <= cp <= 0x1F1FF or cp in _FLAG_BASES or not _is_emoji_base(cp):
            return None  # regional indicators (country flags), other flags, or not an emoji
        cluster = [cp]
        i += 1
        while i < len(cps):
            nxt = cps[i]
            if nxt == _VS16 or 0x1F3FB <= nxt <= 0x1F3FF:      # presentation selector, skin tone
                cluster.append(nxt); i += 1
            elif nxt == _ZWJ and i + 1 < len(cps) and _is_emoji_base(cps[i + 1]):  # family, professions…
                cluster += [nxt, cps[i + 1]]; i += 2
            elif 0xE0020 <= nxt <= 0xE007F or nxt == _KEYCAP:  # subdivision-flag tags, keycaps
                return None
            else:
                break
        out.append("".join(map(chr, cluster)))
    return out


def normalize(text: str) -> Optional[tuple[str, str]]:
    """(the three emojis as typed, an order-independent key) or None if it isn't exactly
    three different non-flag emojis."""
    parts = split(text)
    if parts is None or len(parts) != 3 or len(set(parts)) != 3:
        return None
    strip = lambda e: e.replace(chr(_VS16), "")
    return "".join(parts), "".join(sorted(strip(p) for p in parts))


def roll() -> str:
    """Three different emojis from the pool."""
    pool = list(POOL)
    return "".join(pool.pop(secrets.randbelow(len(pool))) for _ in range(3))
