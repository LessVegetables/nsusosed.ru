// API error code → text for the user. This is the one place to edit when the
// backend adds a code (see "API error codes" in backend/README.md).
//
// Never show error.message from the API: it is a Russian fallback for debugging.

export const ERROR_MESSAGES = {
  AUTH_REQUIRED: {
    ru: 'Сессия закончилась. Войдите снова.',
    en: 'Your session has ended. Please log in again.',
  },
  INVALID_CODE: {
    ru: 'Неверный или просроченный код. Проверьте код или запросите новый.',
    en: 'Wrong or expired code. Check it or request a new one.',
  },
  FORBIDDEN: {
    ru: 'Это действие вам недоступно.',
    en: 'You can’t do that.',
  },
  OWNER_CANNOT_LEAVE: {
    ru: 'Вы автор карточки этой комнаты. Чтобы уйти, удалите карточку на странице «Моя карточка».',
    en: 'You are the author of this room’s listing. To leave, delete the listing on the “My listing” page.',
  },
  NOT_FOUND: {
    ru: 'Не найдено. Карточка могла быть удалена, скрыта или больше вам не подходит.',
    en: 'Not found. The listing may have been deleted or hidden, or it no longer suits you.',
  },
  INVITE_INVALID: {
    ru: 'Приглашение недействительно. Попросите автора карточки прислать новую ссылку.',
    en: 'This invite link is not valid. Ask the listing’s author for a new one.',
  },
  INVITE_EXPIRED: {
    ru: 'Срок действия приглашения истёк. Попросите автора карточки прислать новую ссылку.',
    en: 'This invite link has expired. Ask the listing’s author for a new one.',
  },
  VERSION_CONFLICT: {
    ru: 'Данные успели измениться (например, в другой вкладке). Мы загрузили актуальную версию — проверьте и повторите.',
    en: 'The data changed in the meantime (for example, in another tab). We loaded the latest version: check it and try again.',
  },
  LISTING_EXISTS: {
    ru: 'У вас уже есть карточка. Можно иметь только одну.',
    en: 'You already have a listing. You can only have one.',
  },
  ROOM_TAKEN: {
    ru: 'Для этой комнаты в этом корпусе уже есть карточка. Попросите её автора прислать вам приглашение.',
    en: 'This room in this building already has a listing. Ask its author to send you an invite.',
  },
  ALREADY_IN_ROOM: {
    ru: 'Вы уже живёте в другой комнате на сайте. Сначала выйдите из неё на странице «Аккаунт».',
    en: 'You are already a resident of another room. Leave it first on the “Account” page.',
  },
  ROOM_FULL: {
    ru: 'В комнате уже указано столько жильцов, сколько занятых мест. Попросите автора обновить карточку.',
    en: 'This room already has as many residents as occupied places. Ask the author to update the listing.',
  },
  OCCUPANCY_CONFLICT: {
    ru: 'Занятых мест не может быть меньше, чем жильцов, уже присоединившихся к карточке.',
    en: 'Occupied places can’t be fewer than the residents who have already joined.',
  },
  VALIDATION_ERROR: {
    ru: 'Проверьте отмеченные поля.',
    en: 'Please check the highlighted fields.',
  },
  PROFILE_REQUIRED: {
    ru: 'Сначала заполните анкету.',
    en: 'Please fill in the questionnaire first.',
  },
  BUDGET_REQUIRED: {
    ru: 'Чтобы видеть квартиры, укажите в анкете месячный бюджет.',
    en: 'To see apartments, set a monthly budget in your questionnaire.',
  },
  RATE_LIMITED: {
    ru: 'Слишком много попыток. Повторите через {wait}.',
    en: 'Too many attempts. Try again in {wait}.',
  },
  EMAIL_SEND_FAILED: {
    ru: 'Не удалось отправить письмо с кодом. Попробуйте позже.',
    en: 'We couldn’t send the email with your code. Please try again later.',
  },
  UNSUPPORTED_MEDIA_TYPE: {
    ru: 'Сайт отправил запрос в неверном формате. Обновите страницу.',
    en: 'The site sent a request in the wrong format. Please reload the page.',
  },
  PAYLOAD_TOO_LARGE: {
    ru: 'Слишком много данных. Сократите текст.',
    en: 'Too much data. Please shorten the text.',
  },
  INTERNAL_ERROR: {
    ru: 'Что-то пошло не так на сервере. Попробуйте ещё раз.',
    en: 'Something went wrong on the server. Please try again.',
  },
  // Codes the frontend makes up itself (api.js), not sent by the backend.
  NETWORK_ERROR: {
    ru: 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.',
    en: 'Can’t reach the server. Check your connection and try again.',
  },
  SERVICE_UNAVAILABLE: {
    ru: 'Сервер временно недоступен. Попробуйте через минуту.',
    en: 'The server is temporarily unavailable. Please try again in a minute.',
  },
  UNKNOWN: {
    ru: 'Не удалось выполнить действие. Попробуйте ещё раз.',
    en: 'That didn’t work. Please try again.',
  },
};

// Reasons in error.fields (VALIDATION_ERROR), shown next to the field.
export const FIELD_REASONS = {
  REQUIRED: { ru: 'Обязательное поле.', en: 'Required.' },
  MISSING: { ru: 'Обязательное поле.', en: 'Required.' },
  MUST_BE_EMPTY: { ru: 'Это поле здесь не нужно.', en: 'This field doesn’t apply here.' },
  INVALID_CHOICE: { ru: 'Выберите один из вариантов.', en: 'Choose one of the options.' },
  EXCEEDS_CAPACITY: {
    ru: 'Занятых мест не может быть больше, чем всего мест.',
    en: 'Occupied places can’t exceed the total.',
  },
  INVALID_TELEGRAM: {
    ru: 'Укажите имя пользователя Telegram: 5–32 символа, латиница, цифры и _.',
    en: 'Enter a Telegram username: 5–32 characters, Latin letters, digits and _.',
  },
  INVALID_PHONE: {
    ru: 'Укажите номер телефона, например +7 999 123-45-67.',
    en: 'Enter a phone number, for example +7 999 123-45-67.',
  },
  TOO_LONG: { ru: 'Слишком длинно.', en: 'Too long.' },
  DOMAIN_NOT_ALLOWED: {
    ru: 'Нужна университетская почта @g.nsu.ru.',
    en: 'Use your university email (@g.nsu.ru).',
  },
  INVALID_EMAIL: { ru: 'Это не похоже на адрес почты.', en: 'This doesn’t look like an email address.' },
  MUST_ACCEPT: {
    ru: 'Нужно согласие на обработку персональных данных.',
    en: 'You need to accept the personal data policy.',
  },
  MUST_BE_DELETE: { ru: 'Введите DELETE заглавными буквами.', en: 'Type DELETE in capital letters.' },
  REQUIRED_WHEN_HARD: {
    ru: 'Отметьте хотя бы один подходящий ответ или выключите жёсткое условие.',
    en: 'Tick at least one acceptable answer, or turn the hard condition off.',
  },
  DUPLICATES: { ru: 'Ответы повторяются.', en: 'Some answers are repeated.' },
  OUT_OF_SCALE: { ru: 'Такого варианта нет.', en: 'That option doesn’t exist.' },
  INVALID_QUESTION_SET: {
    ru: 'Ответьте на все вопросы анкеты.',
    en: 'Answer every question in the questionnaire.',
  },
  UNSUPPORTED_VERSION: {
    ru: 'Анкета устарела. Обновите страницу.',
    en: 'The questionnaire is out of date. Please reload the page.',
  },
  STRING_TOO_SHORT: { ru: 'Слишком коротко.', en: 'Too short.' },
  STRING_TOO_LONG: { ru: 'Слишком длинно.', en: 'Too long.' },
  GREATER_THAN_EQUAL: { ru: 'Слишком маленькое значение.', en: 'The value is too small.' },
  GREATER_THAN: { ru: 'Слишком маленькое значение.', en: 'The value is too small.' },
  LESS_THAN_EQUAL: { ru: 'Слишком большое значение.', en: 'The value is too large.' },
  LESS_THAN: { ru: 'Слишком большое значение.', en: 'The value is too large.' },
  INT_PARSING: { ru: 'Введите целое число.', en: 'Enter a whole number.' },
  INT_FROM_FLOAT: { ru: 'Введите целое число.', en: 'Enter a whole number.' },
  // Shown next to a field for some error codes (see my-listing.js).
  ROOM_TAKEN: {
    ru: 'Для этой комнаты в этом корпусе уже есть карточка.',
    en: 'This room in this building already has a listing.',
  },
  OCCUPANCY_CONFLICT: {
    ru: 'Не может быть меньше, чем жильцов уже присоединилось.',
    en: 'Can’t be fewer than the residents who have already joined.',
  },
  // Reasons the frontend checks itself before sending.
  CODE_FORMAT: { ru: 'Введите 6 цифр из письма.', en: 'Enter the 6 digits from the email.' },
  // Anything not listed above (other pydantic error types).
  INVALID: { ru: 'Недопустимое значение.', en: 'Invalid value.' },
};

// "45 с" / "12 мин" — short units so Russian needs no plural forms.
function formatWait(seconds) {
  const s = Math.max(1, Math.ceil(Number(seconds) || 0));
  if (s < 120) return { ru: `${s} с`, en: `${s} s` };
  const m = Math.ceil(s / 60);
  return { ru: `${m} мин`, en: `${m} min` };
}

function fill(pair, values) {
  const out = {};
  for (const lang of Object.keys(pair)) {
    out[lang] = pair[lang].replace(/\{(\w+)\}/g, (match, name) =>
      name in values ? values[name][lang] : match,
    );
  }
  return out;
}

// {ru, en} text for an ApiError (or any thrown error).
export function errorText(err) {
  const code = err?.code;
  if (code === 'RATE_LIMITED') {
    if (err.retryAfter) return fill(ERROR_MESSAGES.RATE_LIMITED, { wait: formatWait(err.retryAfter) });
    return { ru: 'Слишком много попыток. Подождите немного.', en: 'Too many attempts. Please wait a bit.' };
  }
  return ERROR_MESSAGES[code] || ERROR_MESSAGES.UNKNOWN;
}

export function fieldReasonText(reason) {
  return FIELD_REASONS[reason] || FIELD_REASONS.INVALID;
}
