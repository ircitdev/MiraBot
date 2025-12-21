"""
Music Recommendation Service.
Рекомендует музыку на основе эмоционального состояния пользователя.
Использует UspMusicFinder API для отправки треков.
"""

import random
from typing import Optional, Dict, List, Any
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger


# Треки для каждой эмоции с YouTube ссылками
EMOTION_TRACKS: Dict[str, Dict[str, Any]] = {
    "happy": {
        "score": 4,
        "emoji": "😊",
        "name": "Радость (happy)",
        "tracks": [
            {"title": "Pharrell Williams - Happy", "url": "https://youtu.be/ZbZSe6N_BXs"},
            {"title": "Queen - Don't Stop Me Now", "url": "https://youtu.be/HgzGwKwLmgM"},
            {"title": "ABBA - Dancing Queen", "url": "https://youtu.be/xFrGuyw1V8s"},
            {"title": "Katrina & The Waves - Walking on Sunshine", "url": "https://youtu.be/iPUmE-tne5U"},
        ],
    },
    "calm": {
        "score": 2,
        "emoji": "😌",
        "name": "Спокойствие (calm)",
        "tracks": [
            {"title": "Ludovico Einaudi - Nuvole Bianche", "url": "https://youtu.be/4VR-6AS0-l4"},
            {"title": "Yann Tiersen - Comptine d'un autre été", "url": "https://youtu.be/NvryolGa19A"},
            {"title": "Enya - Only Time", "url": "https://youtu.be/7wfYIMyS_dI"},
            {"title": "Norah Jones - Come Away With Me", "url": "https://youtu.be/lbjZPFBD6JU"},
        ],
    },
    "neutral": {
        "score": 0,
        "emoji": "😐",
        "name": "Нейтрально (neutral)",
        "tracks": [
            {"title": "Coldplay - Yellow", "url": "https://youtu.be/yKNxeF4KMsY"},
            {"title": "Jack Johnson - Better Together", "url": "https://youtu.be/seZMOTGCDag"},
            {"title": "Ed Sheeran - Photograph", "url": "https://youtu.be/nSDgHBxUbVQ"},
            {"title": "The Beatles - Here Comes the Sun", "url": "https://youtu.be/KQetemT1sWc"},
        ],
    },
    "tired": {
        "score": -1,
        "emoji": "😔",
        "name": "Усталость (tired)",
        "tracks": [
            {"title": "Bon Iver - Skinny Love", "url": "https://youtu.be/ssdgFoHLwnk"},
            {"title": "Iron & Wine - Flightless Bird", "url": "https://youtu.be/H3g0d6Cgqyg"},
            {"title": "Billie Eilish - everything i wanted", "url": "https://youtu.be/EgBJmlPo8Xw"},
            {"title": "Sleeping At Last - Saturn", "url": "https://youtu.be/dzNvk80XY9s"},
        ],
    },
    "sad": {
        "score": -2,
        "emoji": "😢",
        "name": "Грусть (sad)",
        "tracks": [
            {"title": "Adele - Someone Like You", "url": "https://youtu.be/hLQl3WQQoQ0"},
            {"title": "Sam Smith - Stay With Me", "url": "https://youtu.be/pB-5XG-DbAA"},
            {"title": "Lewis Capaldi - Someone You Loved", "url": "https://youtu.be/bCuhuePlP8o"},
            {"title": "Kodaline - All I Want", "url": "https://youtu.be/mtf7hC17IBM"},
        ],
    },
    "anxious": {
        "score": -1,
        "emoji": "😰",
        "name": "Тревога (anxious)",
        "tracks": [
            {"title": "Marconi Union - Weightless", "url": "https://youtu.be/UfcAVejslrU"},
            {"title": "Max Richter - On The Nature of Daylight", "url": "https://youtu.be/rVN1B-tUpgs"},
            {"title": "Brian Eno - An Ending", "url": "https://youtu.be/aKw5mbcE7VY"},
            {"title": "Sigur Rós - Hoppípolla", "url": "https://youtu.be/mZTb8WxEW78"},
        ],
    },
    "angry": {
        "score": -3,
        "emoji": "😠",
        "name": "Злость (angry)",
        "tracks": [
            {"title": "Linkin Park - Numb", "url": "https://youtu.be/kXYiU_JCYtU"},
            {"title": "Three Days Grace - I Hate Everything About You", "url": "https://youtu.be/d8ekz_CSBVg"},
            {"title": "Rage Against The Machine - Killing In The Name", "url": "https://youtu.be/bWXazVhlyxQ"},
            {"title": "System Of A Down - Chop Suey", "url": "https://youtu.be/CSvFpBOe8eY"},
        ],
    },
    "excited": {
        "score": 3,
        "emoji": "🤩",
        "name": "Возбуждение (excited)",
        "tracks": [
            {"title": "Daft Punk - Get Lucky", "url": "https://youtu.be/5NV6Rdv1a3I"},
            {"title": "Mark Ronson ft. Bruno Mars - Uptown Funk", "url": "https://youtu.be/OPf0YbXqDm0"},
            {"title": "Imagine Dragons - Believer", "url": "https://youtu.be/7wtfhZwyrcc"},
            {"title": "The Weeknd - Blinding Lights", "url": "https://youtu.be/4NRXx6U8ABQ"},
        ],
    },
}

# Жанры музыки с YouTube плейлистами
GENRE_TRACKS: Dict[str, Dict[str, Any]] = {
    "jazz": {
        "emoji": "🎷",
        "name": "Джаз",
        "tracks": [
            {"title": "Dave Brubeck - Take Five", "url": "https://youtu.be/vmDDOFXSgAs"},
            {"title": "Miles Davis - So What", "url": "https://youtu.be/ylXk1LBvIqU"},
            {"title": "John Coltrane - Giant Steps", "url": "https://youtu.be/30FTr6G53VU"},
            {"title": "Louis Armstrong - What a Wonderful World", "url": "https://youtu.be/A3yCcXgbKrE"},
        ],
    },
    "classical": {
        "emoji": "🎹",
        "name": "Классика",
        "tracks": [
            {"title": "Beethoven - Moonlight Sonata", "url": "https://youtu.be/4Tr0otuiQuU"},
            {"title": "Chopin - Nocturne Op.9 No.2", "url": "https://youtu.be/9E6b3swbnWg"},
            {"title": "Debussy - Clair de Lune", "url": "https://youtu.be/CvFH_6DNRCY"},
            {"title": "Vivaldi - Four Seasons (Spring)", "url": "https://youtu.be/l-dYNttdgl0"},
        ],
    },
    "ambient": {
        "emoji": "🌊",
        "name": "Ambient",
        "tracks": [
            {"title": "Brian Eno - Music for Airports", "url": "https://youtu.be/vNwYtllyt3Q"},
            {"title": "Tycho - Awake", "url": "https://youtu.be/ziAqB9nb_To"},
            {"title": "Boards of Canada - Dayvan Cowboy", "url": "https://youtu.be/A2zKARkpDW4"},
            {"title": "Carbon Based Lifeforms - Supersede", "url": "https://youtu.be/PqjR9xdKvSg"},
        ],
    },
    "nature": {
        "emoji": "🌧",
        "name": "Звуки природы",
        "tracks": [
            {"title": "Rain Sounds - 3 Hours", "url": "https://youtu.be/mPZkdNFkNps"},
            {"title": "Forest Sounds - Birds & Stream", "url": "https://youtu.be/xNN7iTA57jM"},
            {"title": "Ocean Waves - Relaxing", "url": "https://youtu.be/f77SKdyn-1Y"},
            {"title": "Thunderstorm Sounds", "url": "https://youtu.be/nDq6TstdEi8"},
        ],
    },
}

# Маппинг похожих эмоций для fallback
EMOTION_ALIASES = {
    "joy": "happy",
    "happiness": "happy",
    "радость": "happy",
    "счастье": "happy",
    "peace": "calm",
    "relaxed": "calm",
    "спокойствие": "calm",
    "покой": "calm",
    "fatigue": "tired",
    "exhausted": "tired",
    "усталость": "tired",
    "sadness": "sad",
    "грусть": "sad",
    "печаль": "sad",
    "anxiety": "anxious",
    "worried": "anxious",
    "тревога": "anxious",
    "anger": "angry",
    "frustrated": "angry",
    "злость": "angry",
    "excitement": "excited",
    "энергия": "excited",
}


class MusicRecommendationService:
    """Сервис рекомендации музыки по эмоциям."""

    def __init__(self, bot: Bot = None):
        self.bot = bot

    def set_bot(self, bot: Bot):
        """Устанавливает экземпляр бота."""
        self.bot = bot

    def normalize_emotion(self, emotion: str) -> str:
        """Нормализует название эмоции к стандартному виду."""
        emotion_lower = emotion.lower().strip()

        # Проверяем прямое совпадение
        if emotion_lower in EMOTION_TRACKS:
            return emotion_lower

        # Проверяем алиасы
        if emotion_lower in EMOTION_ALIASES:
            return EMOTION_ALIASES[emotion_lower]

        # По умолчанию - neutral
        return "neutral"

    def get_random_track(self, emotion: str) -> Optional[Dict[str, str]]:
        """
        Возвращает случайный трек для эмоции.

        Args:
            emotion: Название эмоции (happy, calm, sad, etc.)

        Returns:
            {"title": str, "url": str} или None
        """
        normalized = self.normalize_emotion(emotion)

        if normalized not in EMOTION_TRACKS:
            return None

        tracks = EMOTION_TRACKS[normalized]["tracks"]
        if not tracks:
            return None

        return random.choice(tracks)

    def get_random_track_by_genre(self, genre: str) -> Optional[Dict[str, str]]:
        """
        Возвращает случайный трек для жанра.

        Args:
            genre: Жанр (jazz, classical, ambient, nature)

        Returns:
            {"title": str, "url": str} или None
        """
        genre_lower = genre.lower().strip()

        # Маппинг русских названий
        genre_aliases = {
            "джаз": "jazz",
            "классика": "classical",
            "классическая": "classical",
            "эмбиент": "ambient",
            "амбиент": "ambient",
            "природа": "nature",
            "звуки природы": "nature",
        }

        if genre_lower in genre_aliases:
            genre_lower = genre_aliases[genre_lower]

        if genre_lower not in GENRE_TRACKS:
            return None

        tracks = GENRE_TRACKS[genre_lower]["tracks"]
        if not tracks:
            return None

        return random.choice(tracks)

    def get_emotion_info(self, emotion: str) -> Optional[Dict[str, Any]]:
        """Возвращает информацию об эмоции."""
        normalized = self.normalize_emotion(emotion)
        return EMOTION_TRACKS.get(normalized)

    async def recommend_music_by_emotion(
        self,
        chat_id: int,
        emotion: str,
        send_track: bool = True,
    ) -> Dict[str, Any]:
        """
        Рекомендует музыку на основе эмоции.

        Args:
            chat_id: ID чата пользователя
            emotion: Текущая эмоция пользователя
            send_track: Отправлять ли трек через API

        Returns:
            {
                "success": bool,
                "track": str,
                "emotion": str,
                "message": str,
            }
        """
        normalized = self.normalize_emotion(emotion)
        track = self.get_random_track(normalized)

        if not track:
            return {
                "success": False,
                "track": None,
                "emotion": normalized,
                "message": "Не удалось подобрать трек",
            }

        emotion_info = EMOTION_TRACKS.get(normalized, {})
        emoji = emotion_info.get("emoji", "🎵")

        # Формируем сообщение
        messages = {
            "happy": [
                f"{emoji} Для твоего отличного настроения:",
                f"{emoji} Поддержу твою радость музыкой:",
                f"{emoji} Вот что поднимет настроение ещё выше:",
            ],
            "calm": [
                f"{emoji} Для спокойствия и гармонии:",
                f"{emoji} Музыка для расслабления:",
                f"{emoji} Сохрани это спокойствие:",
            ],
            "neutral": [
                f"{emoji} Может, это тебе понравится:",
                f"{emoji} Послушай:",
                f"{emoji} Вот хорошая музыка для тебя:",
            ],
            "tired": [
                f"{emoji} Отдохни под эту музыку:",
                f"{emoji} Для восстановления сил:",
                f"{emoji} Немного музыки для отдыха:",
            ],
            "sad": [
                f"{emoji} Понимаю твои чувства. Вот музыка:",
                f"{emoji} Иногда нужно погрустить. Послушай:",
                f"{emoji} Музыка, которая понимает:",
            ],
            "anxious": [
                f"{emoji} Эта музыка поможет успокоиться:",
                f"{emoji} Для снятия тревоги:",
                f"{emoji} Дыши глубже и послушай:",
            ],
            "angry": [
                f"{emoji} Выпусти эмоции с этой музыкой:",
                f"{emoji} Иногда нужно выплеснуть злость:",
                f"{emoji} Музыка для настроения:",
            ],
            "excited": [
                f"{emoji} Для твоей энергии:",
                f"{emoji} Драйв и позитив:",
                f"{emoji} Продолжай в том же духе:",
            ],
        }

        message = random.choice(messages.get(normalized, [f"{emoji} Послушай:"]))

        # Теперь track — это dict с title и url
        return {
            "success": True,
            "track": track["title"],
            "url": track["url"],
            "emotion": normalized,
            "message": message,
        }

    async def recommend_music_by_genre(
        self,
        genre: str,
    ) -> Dict[str, Any]:
        """
        Рекомендует музыку по жанру.

        Args:
            genre: Жанр музыки (jazz, classical, ambient, nature)

        Returns:
            {
                "success": bool,
                "track": str,
                "url": str,
                "genre": str,
                "message": str,
            }
        """
        track = self.get_random_track_by_genre(genre)

        if not track:
            return {
                "success": False,
                "track": None,
                "url": None,
                "genre": genre,
                "message": f"Нет треков для жанра: {genre}",
            }

        # Определяем emoji и сообщение
        genre_lower = genre.lower()
        genre_aliases = {
            "джаз": "jazz",
            "классика": "classical",
            "классическая": "classical",
            "эмбиент": "ambient",
            "амбиент": "ambient",
            "природа": "nature",
            "звуки природы": "nature",
        }
        if genre_lower in genre_aliases:
            genre_lower = genre_aliases[genre_lower]

        genre_info = GENRE_TRACKS.get(genre_lower, {})
        emoji = genre_info.get("emoji", "🎵")
        genre_name = genre_info.get("name", genre)

        messages = [
            f"{emoji} Держи **{genre_name}**:",
            f"{emoji} Отличный выбор! Вот **{genre_name}**:",
            f"{emoji} Для тебя — **{genre_name}**:",
        ]

        return {
            "success": True,
            "track": track["title"],
            "url": track["url"],
            "genre": genre_name,
            "message": random.choice(messages),
        }

    def get_all_emotions(self) -> List[Dict[str, Any]]:
        """Возвращает список всех эмоций с треками."""
        return [
            {
                "key": key,
                "name": info["name"],
                "emoji": info["emoji"],
                "score": info["score"],
                "tracks_count": len(info["tracks"]),
                "films_count": len(info.get("films", [])),
            }
            for key, info in EMOTION_TRACKS.items()
        ]


# Глобальный экземпляр
music_recommendation = MusicRecommendationService()


def detect_music_request(text: str) -> bool:
    """Определяет, является ли текст запросом музыки."""
    text_lower = text.lower()

    music_keywords = [
        "посоветуй музыку",
        "порекомендуй музыку",
        "что послушать",
        "включи музыку",
        "поставь музыку",
        "хочу музыку",
        "дай музыку",
        "музыку под настроение",
        "recommend music",
        "play music",
    ]

    return any(kw in text_lower for kw in music_keywords)
