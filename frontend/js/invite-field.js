// The invite field: whatever is pasted in (the code, the whole link, or the message the link
// came in), only the code stays in the box. The server reads links too (parse_invite_code in
// backend/app/services/home_service.py); this is so the person sees what will be sent.

import { t } from './i18n.js';

const IN_LINK = /code=([A-Za-z0-9]+)/;
// Codes use these letters only (no 0/O, 1/I/L); see _CODE_ALPHABET on the server.
const CODE_WORD = /\b[A-HJKMNP-Za-hjkmnp-z2-9]{8}\b/g;
const CODE_LENGTH = 8;

/** The code inside a pasted text, uppercased, or the text itself cleaned up. */
export function inviteCode(text) {
  const link = IN_LINK.exec(text);
  if (link) return link[1].toUpperCase();
  const bare = text.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  if (bare.length <= CODE_LENGTH) return bare;
  // A longer text ("here's the code: K7QM2XWP"): the code-like word, preferring one with a digit.
  const words = text.match(CODE_WORD) ?? [];
  const word = words.find((w) => /\d/.test(w)) ?? (words.length === 1 ? words[0] : null);
  return word ? word.toUpperCase() : bare;
}

/**
 * Make an <input> keep only the code. `hint` (optional) is the <small> under it: it briefly
 * says the link was turned into the code, then goes back to its own text (or hides again).
 */
export function mountInviteField(input, hint = null) {
  const hintText = hint?.textContent ?? '';
  const hintHidden = hint?.hidden ?? true;
  let timer;

  function clean() {
    const raw = input.value;
    const code = inviteCode(raw);
    if (code === raw) return;
    // Typing (letters uppercased, spaces dropped): keep the caret where it was.
    const typed = !IN_LINK.test(raw) && raw.replace(/[^A-Za-z0-9]/g, '').toUpperCase() === code;
    const caret = typed ? inviteCode(raw.slice(0, input.selectionStart ?? raw.length)).length : code.length;
    input.value = code;
    input.setSelectionRange(caret, caret);
    if (hint && !typed && code) {
      hint.textContent = t('join.fromLink');
      hint.hidden = false;
      clearTimeout(timer);
      timer = setTimeout(() => {
        hint.textContent = hint.dataset.i18n ? t(hint.dataset.i18n) : hintText; // the language may have changed
        hint.hidden = hintHidden;
      }, 4000);
    }
  }

  input.addEventListener('input', clean);
  clean(); // a value put in before (from the address or the browser's autofill)
}
