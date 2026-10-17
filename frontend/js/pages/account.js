// /account — display name, leave a room, log out, delete the account.

import { api } from '../api.js';
import { initPage } from '../layout.js';
import { session } from '../storage.js';
import { busy, clearError, clearFieldErrors, confirmDialog, showError, showFieldErrors, toast } from '../ui.js';

const { me } = await initPage({ auth: 'required' });

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
    const updated = await api.updateMe(name);
    nameInput.value = updated.display_name;
    toast('account.nameSaved');
  } catch (err) {
    if (err.code === 'VALIDATION_ERROR') showFieldErrors(nameForm, err.fields);
    showError(nameError, err);
  } finally {
    done();
  }
});

// ---- Leave the room the user joined as a resident
const leaveButton = document.getElementById('leave');
const leaveError = document.getElementById('leave-error');
leaveButton.addEventListener('click', async () => {
  const ok = await confirmDialog({ title: 'account.leaveTitle', body: 'account.leaveBody', confirm: 'account.leave' });
  if (!ok) return;
  clearError(leaveError);
  const done = busy(leaveButton);
  try {
    await api.leaveRoom();
    toast('account.left');
  } catch (err) {
    showError(leaveError, err);
  } finally {
    done();
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
