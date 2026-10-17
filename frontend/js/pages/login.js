// /login — email → one-time code → session cookie.

import { api } from '../api.js';
import { EMAIL_DOMAIN, RESEND_COOLDOWN_SECONDS } from '../config.js';
import { bindText } from '../i18n.js';
import { initPage } from '../layout.js';
import { busy, clearError, clearFieldErrors, mmss, safeNext, showError, showFieldErrors } from '../ui.js';

const params = new URLSearchParams(location.search);
const next = safeNext(params.get('next'));

const { me } = await initPage({ auth: 'optional' });
if (me) location.replace(next);

const stepEmail = document.getElementById('step-email');
const stepCode = document.getElementById('step-code');
const emailForm = document.getElementById('email-form');
const codeForm = document.getElementById('code-form');
const emailInput = document.getElementById('email');
const privacyInput = document.getElementById('privacy');
const codeInput = document.getElementById('code');
const emailError = document.getElementById('email-error');
const codeError = document.getElementById('code-error');
const codeSent = document.getElementById('code-sent');
const codeTimer = document.getElementById('code-timer');
const resendButton = document.getElementById('resend');

let email = '';
let codeExpiresAt = 0;
let resendAt = 0;
let timer = null;
let verifying = false;

const secondsLeft = (until) => (until - Date.now()) / 1000;

function tick() {
  const codeLeft = secondsLeft(codeExpiresAt);
  if (codeLeft > 0) bindText(codeTimer, 'login.codeValid', { time: mmss(codeLeft) });
  else bindText(codeTimer, 'login.codeExpired');

  const resendLeft = secondsLeft(resendAt);
  resendButton.disabled = resendLeft > 0;
  if (resendLeft > 0) bindText(resendButton, 'login.resendIn', { time: mmss(resendLeft) });
  else bindText(resendButton, 'login.resend');
}

function startTimers(ttlSeconds, cooldownSeconds) {
  codeExpiresAt = Date.now() + ttlSeconds * 1000;
  resendAt = Date.now() + cooldownSeconds * 1000;
  clearInterval(timer);
  timer = setInterval(tick, 1000);
  tick();
}

// Let the user resend once the server says it's allowed again.
function holdResend(seconds) {
  resendAt = Date.now() + seconds * 1000;
  tick();
}

function isUniversityEmail(value) {
  return new RegExp(`^[^\\s@]+@${EMAIL_DOMAIN.replace(/\./g, '\\.')}$`, 'i').test(value);
}

async function sendCode(errorTarget, form) {
  const result = await api.requestCode(email, true);
  bindText(codeSent, 'login.codeSent', { email: result.email_masked });
  startTimers(result.ttl_seconds, RESEND_COOLDOWN_SECONDS);
  clearError(errorTarget);
  if (form) clearFieldErrors(form);
}

emailForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError(emailError);
  email = emailInput.value.trim();

  if (!email) return showFieldErrors(emailForm, { email: 'REQUIRED' });
  if (!isUniversityEmail(email)) {
    return showFieldErrors(emailForm, { email: email.includes('@') ? 'DOMAIN_NOT_ALLOWED' : 'INVALID_EMAIL' });
  }
  if (!privacyInput.checked) return showFieldErrors(emailForm, { privacy_accepted: 'MUST_ACCEPT' });
  clearFieldErrors(emailForm);

  const done = busy(emailForm.querySelector('[type="submit"]'));
  try {
    await sendCode(emailError, emailForm);
    stepEmail.hidden = true;
    stepCode.hidden = false;
    codeInput.value = '';
    codeInput.focus();
  } catch (err) {
    if (err.code === 'VALIDATION_ERROR') showFieldErrors(emailForm, err.fields);
    showError(emailError, err);
  } finally {
    done();
  }
});

resendButton.addEventListener('click', async () => {
  clearError(codeError);
  const done = busy(resendButton);
  try {
    await sendCode(codeError);
    codeInput.value = '';
    codeInput.focus();
  } catch (err) {
    if (err.code === 'RATE_LIMITED' && err.retryAfter) holdResend(err.retryAfter);
    showError(codeError, err);
  } finally {
    done();
    tick();
  }
});

document.getElementById('change-email').addEventListener('click', () => {
  clearInterval(timer);
  clearError(codeError);
  clearFieldErrors(codeForm);
  stepCode.hidden = true;
  stepEmail.hidden = false;
  emailInput.focus();
});

async function verify() {
  if (verifying) return;
  const code = codeInput.value.replace(/\D/g, '');
  clearError(codeError);
  if (code.length !== 6) {
    showFieldErrors(codeForm, { code: 'CODE_FORMAT' });
    return;
  }
  clearFieldErrors(codeForm);

  verifying = true;
  const done = busy(codeForm.querySelector('[type="submit"]'));
  try {
    const result = await api.verifyCode(email, code);
    clearInterval(timer);
    if (!result.profile_complete && !next.startsWith('/questionnaire')) {
      location.assign(`/questionnaire?next=${encodeURIComponent(next)}`);
    } else {
      location.assign(next);
    }
  } catch (err) {
    showError(codeError, err);
    codeInput.select();
    done();
    verifying = false;
  }
}

codeForm.addEventListener('submit', (event) => {
  event.preventDefault();
  verify();
});

// Submit as soon as all 6 digits are in (typed or pasted).
codeInput.addEventListener('input', () => {
  const digits = codeInput.value.replace(/\D/g, '').slice(0, 6);
  if (digits !== codeInput.value) codeInput.value = digits;
  if (digits.length === 6) verify();
});

// The buttons start disabled in the HTML so the form can't be submitted
// natively (which would put the email in the URL) before this script runs.
for (const button of document.querySelectorAll('form [type="submit"]')) button.disabled = false;
