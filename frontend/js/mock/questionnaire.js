// Copy of backend/app/config/questionnaire_v1.json (feature/backend_fixes), used
// only by the mock API. The real list always comes from GET /api/questions.

export default {
  "version": 1,
  "questions": [
    {
      "key": "sleep",
      "label": {
        "ru": "Во сколько вы обычно ложитесь спать?",
        "en": "What time do you usually go to bed?"
      },
      "scale": [
        {
          "value": 0,
          "label": {
            "ru": "до 22:00",
            "en": "before 22:00"
          }
        },
        {
          "value": 1,
          "label": {
            "ru": "с 22:00 до 23:00",
            "en": "22:00–23:00"
          }
        },
        {
          "value": 2,
          "label": {
            "ru": "с 23:00 до 00:00",
            "en": "23:00–00:00"
          }
        },
        {
          "value": 3,
          "label": {
            "ru": "с 00:00 до 01:00",
            "en": "00:00–01:00"
          }
        },
        {
          "value": 4,
          "label": {
            "ru": "с 01:00 и позже",
            "en": "01:00 or later"
          }
        }
      ],
      "min_value": 0,
      "max_value": 4,
      "normalize_divisor": 4
    },
    {
      "key": "noise",
      "label": {
        "ru": "Как часто у вас бывает шум ночью?",
        "en": "How often are you noisy at night?"
      },
      "scale": [
        {
          "value": 0,
          "label": {
            "ru": "никогда",
            "en": "never"
          }
        },
        {
          "value": 1,
          "label": {
            "ru": "реже раза в неделю",
            "en": "less than once a week"
          }
        },
        {
          "value": 2,
          "label": {
            "ru": "1-2 ночи в неделю",
            "en": "1–2 nights a week"
          }
        },
        {
          "value": 3,
          "label": {
            "ru": "3-4 ночи",
            "en": "3–4 nights a week"
          }
        },
        {
          "value": 4,
          "label": {
            "ru": "почти каждую ночь",
            "en": "almost every night"
          }
        }
      ],
      "min_value": 0,
      "max_value": 4,
      "normalize_divisor": 4
    },
    {
      "key": "cleanliness",
      "label": {
        "ru": "Как часто вы делаете уборку?",
        "en": "How often do you clean?"
      },
      "scale": [
        {
          "value": 0,
          "label": {
            "ru": "реже раза в месяц",
            "en": "less than once a month"
          }
        },
        {
          "value": 1,
          "label": {
            "ru": "раз в месяц",
            "en": "once a month"
          }
        },
        {
          "value": 2,
          "label": {
            "ru": "раз в две недели",
            "en": "every two weeks"
          }
        },
        {
          "value": 3,
          "label": {
            "ru": "еженедельно",
            "en": "weekly"
          }
        },
        {
          "value": 4,
          "label": {
            "ru": "ежедневно",
            "en": "daily"
          }
        }
      ],
      "min_value": 0,
      "max_value": 4,
      "normalize_divisor": 4
    },
    {
      "key": "guests",
      "label": {
        "ru": "Как часто вы приглашаете гостей?",
        "en": "How often do you have guests over?"
      },
      "scale": [
        {
          "value": 0,
          "label": {
            "ru": "не приглашаю",
            "en": "I don't"
          }
        },
        {
          "value": 1,
          "label": {
            "ru": "реже раза в неделю",
            "en": "less than once a week"
          }
        },
        {
          "value": 2,
          "label": {
            "ru": "1-2 дня в неделю",
            "en": "1–2 days a week"
          }
        },
        {
          "value": 3,
          "label": {
            "ru": "3-4 дня",
            "en": "3–4 days a week"
          }
        },
        {
          "value": 4,
          "label": {
            "ru": "почти каждый день",
            "en": "almost every day"
          }
        }
      ],
      "min_value": 0,
      "max_value": 4,
      "normalize_divisor": 4
    },
    {
      "key": "smoking",
      "label": {
        "ru": "Курение в комнате?",
        "en": "Smoking in the room?"
      },
      "scale": [
        {
          "value": 0,
          "label": {
            "ru": "нет",
            "en": "no"
          }
        },
        {
          "value": 1,
          "label": {
            "ru": "да",
            "en": "yes"
          }
        }
      ],
      "min_value": 0,
      "max_value": 1,
      "normalize_divisor": 1
    },
    {
      "key": "alcohol",
      "label": {
        "ru": "Употребление алкоголя в комнате?",
        "en": "Drinking alcohol in the room?"
      },
      "scale": [
        {
          "value": 0,
          "label": {
            "ru": "никогда",
            "en": "never"
          }
        },
        {
          "value": 1,
          "label": {
            "ru": "реже раза в месяц",
            "en": "less than once a month"
          }
        },
        {
          "value": 2,
          "label": {
            "ru": "1-3 дня в месяц",
            "en": "1–3 days a month"
          }
        },
        {
          "value": 3,
          "label": {
            "ru": "еженедельно",
            "en": "weekly"
          }
        },
        {
          "value": 4,
          "label": {
            "ru": "несколько дней в неделю",
            "en": "several days a week"
          }
        }
      ],
      "min_value": 0,
      "max_value": 4,
      "normalize_divisor": 4
    },
    {
      "key": "study",
      "label": {
        "ru": "Учёба в комнате в тишине?",
        "en": "How often do you study in the room and need quiet?"
      },
      "scale": [
        {
          "value": 0,
          "label": {
            "ru": "не учусь",
            "en": "I don't"
          }
        },
        {
          "value": 1,
          "label": {
            "ru": "реже раза в неделю",
            "en": "less than once a week"
          }
        },
        {
          "value": 2,
          "label": {
            "ru": "1-2 дня",
            "en": "1–2 days a week"
          }
        },
        {
          "value": 3,
          "label": {
            "ru": "3-4 дня",
            "en": "3–4 days a week"
          }
        },
        {
          "value": 4,
          "label": {
            "ru": "почти ежедневно",
            "en": "almost every day"
          }
        }
      ],
      "min_value": 0,
      "max_value": 4,
      "normalize_divisor": 4
    },
    {
      "key": "airing",
      "label": {
        "ru": "Проветривание?",
        "en": "How often do you air the room?"
      },
      "scale": [
        {
          "value": 0,
          "label": {
            "ru": "практически не открываю",
            "en": "almost never open the window"
          }
        },
        {
          "value": 1,
          "label": {
            "ru": "несколько раз в неделю",
            "en": "a few times a week"
          }
        },
        {
          "value": 2,
          "label": {
            "ru": "раз в день",
            "en": "once a day"
          }
        },
        {
          "value": 3,
          "label": {
            "ru": "дважды в день",
            "en": "twice a day"
          }
        },
        {
          "value": 4,
          "label": {
            "ru": "чаще двух раз в день",
            "en": "more than twice a day"
          }
        }
      ],
      "min_value": 0,
      "max_value": 4,
      "normalize_divisor": 4
    },
    {
      "key": "temperature",
      "label": {
        "ru": "Предпочтение температуры?",
        "en": "What room temperature do you prefer?"
      },
      "scale": [
        {
          "value": 0,
          "label": {
            "ru": "очень прохладно",
            "en": "very cool"
          }
        },
        {
          "value": 1,
          "label": {
            "ru": "прохладно",
            "en": "cool"
          }
        },
        {
          "value": 2,
          "label": {
            "ru": "умеренно",
            "en": "moderate"
          }
        },
        {
          "value": 3,
          "label": {
            "ru": "тепло",
            "en": "warm"
          }
        },
        {
          "value": 4,
          "label": {
            "ru": "очень тепло",
            "en": "very warm"
          }
        }
      ],
      "min_value": 0,
      "max_value": 4,
      "normalize_divisor": 4
    }
  ]
};
