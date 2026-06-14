"""
Keyword-based detector for vision queries.
ADR-005: Vision triggered ONLY on explicit user request.
No LLM needed — pure substring matching.
"""
from __future__ import annotations

EVENT_VISION_ANSWERED = "vision.answered"

_VISION_TRIGGERS = [
    "посмотри на экран",
    "посмотри на мой экран",
    "что на экране",
    "что ты видишь",
    "что видишь на экране",
    "опиши экран",
    "опиши что на экране",
    "look at the screen",
    "what do you see",
    "describe the screen",
    "что происходит на экране",
    "что открыто",
    "какие окна открыты",
    "analyze screen",
    "анализируй экран",
    "сфотографируй экран",
    "сделай скриншот",
    "take a screenshot",
]

_FIND_TRIGGERS = [
    "найди на экране",
    "find on screen",
    "где на экране",
    "where on screen",
    "найди кнопку",
    "найди элемент",
    "find element",
    "find button",
]


class VisionTrigger:
    """Detects whether a user utterance requires vision analysis."""

    def is_vision_query(self, text: str) -> bool:
        lower = text.lower()
        return any(trigger in lower for trigger in _VISION_TRIGGERS)

    def is_find_query(self, text: str) -> bool:
        lower = text.lower()
        return any(trigger in lower for trigger in _FIND_TRIGGERS)

    def extract_element(self, text: str) -> str:
        """Extract the element name from a 'find X on screen' query."""
        lower = text.lower()
        for trigger in _FIND_TRIGGERS:
            if trigger in lower:
                # Take the part after the trigger phrase
                idx = lower.index(trigger) + len(trigger)
                return text[idx:].strip().strip("?.,!")
        return text.strip()
