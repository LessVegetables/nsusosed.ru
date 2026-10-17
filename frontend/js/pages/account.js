// /account — display name, interface language, log out, delete the account.
// Leaving a home is on /home.

import { api } from '../api.js';
import { getLang, setLang } from '../i18n.js';
import { initPage } from '../layout.js';
import { session } from '../storage.js';
import { busy, clearError, clearFieldErrors, showError, showFieldErrors, toast } from '../ui.js';

const { me } = await initPage({ auth: 'required', onboarding: true });

// ---- Display name
const nameForm = document.getElementById('name-form');
const nameInput = document.getElementById('display-name');
const nameError = document.getElementById('name-error');
document.getElementById('email').textContent = me.email;
nameInput.value = me.display_name;

nameForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError(nameError);
  const name = nameInput.value.trim();
  if (name.length < 2) return showFieldErrors(nameForm, { display_name: 'STRING_TOO_SHORT' });
  if (name.length > 60) return showFieldErrors(nameForm, { display_name: 'STRING_TOO_LONG' });
  clearFieldErrors(nameForm);

  const done = busy(nameForm.querySelector('[type="submit"]'));
  try {
    const updated = await api.updateMe({ display_name: name });
    nameInput.value = updated.display_name;
    toast('account.nameSaved');
  } catch (err) {
    if (err.code === 'VALIDATION_ERROR') showFieldErrors(nameForm, err.fields);
    showError(nameError, err);
  } finally {
    done();
  }
});

// ---- Interface language: saved to the account, so it follows the user
const languageSelect = document.getElementById('language');
const languageError = document.getElementById('language-error');
languageSelect.value = getLang();
languageSelect.addEventListener('change', async () => {
  clearError(languageError);
  const lang = languageSelect.value;
  languageSelect.disabled = true;
  try {
    await api.updateMe({ language: lang });
    setLang(lang);
    toast('account.languageSaved');
  } catch (err) {
    languageSelect.value = getLang();
    showError(languageError, err);
  } finally {
    languageSelect.disabled = false;
  }
});

// ---- Log out
const logoutButton = document.getElementById('logout');
logoutButton.addEventListener('click', async () => {
  const done = busy(logoutButton);
  try {
    await api.logout();
    session.remove('nsusosed.invite');
    location.assign('/login');
  } catch (err) {
    showError(document.getElementById('logout-error'), err);
    done();
  }
});

// ---- Delete the account
const deleteForm = document.getElementById('delete-form');
const deleteInput = document.getElementById('delete-confirm');
const deleteButton = deleteForm.querySelector('[type="submit"]');
const deleteError = document.getElementById('delete-error');
deleteInput.addEventListener('input', () => {
  deleteButton.disabled = deleteInput.value.trim() !== 'DELETE';
});
deleteForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError(deleteError);
  if (deleteInput.value.trim() !== 'DELETE') return showFieldErrors(deleteForm, { confirm: 'MUST_BE_DELETE' });
  const done = busy(deleteButton);
  try {
    await api.deleteMe('DELETE');
    session.remove('nsusosed.invite');
    location.assign('/?deleted=1');
  } catch (err) {
    if (err.code === 'VALIDATION_ERROR') showFieldErrors(deleteForm, err.fields);
    showError(deleteError, err);
    done();
  }
});

// Disabled in the HTML until this script is ready (the delete button stays
// disabled until DELETE is typed).
nameForm.querySelector('[type="submit"]').disabled = false;
