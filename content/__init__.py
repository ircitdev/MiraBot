"""
Контент-модуль.
Упражнения, аффирмации, медитации.
"""

from content.exercises import (
    Exercise,
    ExerciseCategory,
    ALL_EXERCISES,
    get_exercise_by_id,
    get_exercises_by_category,
    get_random_exercise,
    get_exercise_for_state,
    format_exercise,
    format_exercise_short,
)

from content.affirmations import (
    get_daily_affirmation,
    get_affirmation_by_category,
    AFFIRMATION_CATEGORIES,
)

__all__ = [
    # Упражнения
    "Exercise",
    "ExerciseCategory",
    "ALL_EXERCISES",
    "get_exercise_by_id",
    "get_exercises_by_category",
    "get_random_exercise",
    "get_exercise_for_state",
    "format_exercise",
    "format_exercise_short",
    # Аффирмации
    "get_daily_affirmation",
    "get_affirmation_by_category",
    "AFFIRMATION_CATEGORIES",
]
