// Starting data for the mock API: other students, their answers and listings.
// Deterministic, so every reset gives the same rooms. Demo invite link:
//   /join#token=demo-invite-token

const DAY_MS = 86_400_000;

// Small seeded random generator (mulberry32).
function random(seed) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function seedDb(questionnaire) {
  const rnd = random(42);
  const pick = (n) => Math.floor(rnd() * n);
  // memberships: {userId: {listing_id, is_admin, joined_at}}
  const db = { session: null, users: {}, profiles: {}, listings: {}, memberships: {}, otp: {} };
  const daysAgo = (d) => new Date(Date.now() - d * DAY_MS).toISOString();
  let n = 0;

  // values: {sleep: 2, ...}; anything missing is random. hard: {smoking: [0]}.
  function person(name, values = {}, hard = {}) {
    n += 1;
    const id = `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
    db.users[id] = { id, email: `student${n}@g.nsu.ru`, display_name: name, language: 'ru' };
    const answers = {};
    for (const q of questionnaire.questions) {
      const max = q.max_value;
      answers[q.key] = {
        value: values[q.key] ?? pick(max + 1),
        importance: 3 + pick(8),
        hard: Boolean(hard[q.key]),
        allowed: hard[q.key] ?? [],
      };
    }
    db.profiles[id] = {
      user_id: id, questionnaire_version: questionnaire.version, answers, situation: 'host',
      budget_max_rub: null, version: 1, updated_at: daysAgo(3),
    };
    return id;
  }

  // A user who joined but hasn't filled in the questionnaire.
  function noProfile(name) {
    const id = person(name);
    delete db.profiles[id];
    return id;
  }

  // The first person is the home's admin.
  function listing(id, admin, residents, fields) {
    const lid = `10000000-0000-4000-8000-${String(id).padStart(12, '0')}`;
    db.listings[lid] = {
      id: lid, status: 'active', version: 3, created_at: daysAgo(40), photos: [],
      confirmed_at: daysAgo(fields.confirmedDaysAgo ?? 2), invite_token: fields.invite_token ?? null,
      invite_expires_at: fields.invite_token ? new Date(Date.now() + 7 * DAY_MS).toISOString() : null,
      building: null, room_number: null, floor: null, is_corner: null, windows_count: null, view: null, layout: null,
      district: null, monthly_cost_per_person_rub: null, description: null,
      contacts: [{ type: 'telegram', value: 'nsu_student' }],
      ...fields,
    };
    delete db.listings[lid].confirmedDaysAgo;
    [admin, ...residents].forEach((uid, i) => {
      db.memberships[uid] = { listing_id: lid, is_admin: i === 0, joined_at: daysAgo(40 - i) };
    });
  }

  const early = { sleep: 1, wake: 1, noise: 0, cleanliness: 3, guests: 1, smoking: 0, alcohol: 0, study: 3, airing: 2, temperature: 2 };
  const owl = { sleep: 4, wake: 4, noise: 3, cleanliness: 1, guests: 3, smoking: 0, alcohol: 2, study: 1, airing: 1, temperature: 3 };

  listing(1, person('Аня', early), [person('Катя', { ...early, sleep: 2 })], {
    kind: 'dorm', building: '7', room_number: 214, floor: 2, capacity: 4, occupied_count: 3,
    is_corner: true, windows_count: 2, view: 'forest', layout: 'Блок на две комнаты, душ в блоке',
    description: 'Тихая комната, рано ложимся. Третья соседка заселится в сентябре.',
    contacts: [{ type: 'telegram', value: 'anya_nsu' }, { type: 'phone', value: '+79131112233' }],
    invite_token: 'demo-invite-token',
  });
  listing(2, person('Дима', owl), [person('Саша', { ...owl, guests: 4 }), noProfile('Миша')], {
    kind: 'dorm', building: '10А', room_number: 512, floor: 5, capacity: 4, occupied_count: 3,
    view: 'road', description: 'Сова-friendly: ложимся поздно, по выходным бывают гости.',
    contacts: [{ type: 'phone', value: '+79991234567' }],
  });
  listing(3, person('Лена', { ...early, sleep: 0 }), [person('Оля', { ...owl, sleep: 4 })], {
    kind: 'dorm', building: '5', room_number: 302, floor: 3, capacity: 3, occupied_count: 2,
    windows_count: 1, view: 'yard', contacts: [{ type: 'whatsapp', value: '+79137654321' }],
  });
  listing(4, person('Рома', { smoking: 1 }, { smoking: [1] }), [], {
    kind: 'dorm', building: '8', room_number: 122, floor: 1, capacity: 2, occupied_count: 1,
    description: 'Курю на балконе, ищу соседа, которого это не смущает.',
    contacts: [{ type: 'max', value: 'roma.max' }],
  });
  listing(5, person('Ира', early), [], {
    kind: 'dorm', building: '4', room_number: 401, floor: 4, capacity: 2, occupied_count: 1,
    confirmedDaysAgo: 27, contacts: [{ type: 'other', value: 'vk.com/ira_nsu' }],
  });
  listing(6, person('Женя', early), [person('Паша')], {
    kind: 'apartment', district: 'Верхняя зона', monthly_cost_per_person_rub: 15000, capacity: 3, occupied_count: 2,
    description: 'Трёшка у Морского проспекта, одна комната свободна.', contacts: [{ type: 'telegram', value: 'zhenya_flat' }],
  });
  listing(7, person('Вика', owl), [], {
    kind: 'apartment', district: 'Щ', monthly_cost_per_person_rub: 25000, capacity: 2, occupied_count: 1,
    contacts: [{ type: 'telegram', value: 'vika_shch' }],
  });
  listing(8, person('Гоша'), [person('Лёша')], {
    kind: 'apartment', district: 'Шлюз', monthly_cost_per_person_rub: 12000, capacity: 4, occupied_count: 2,
    contacts: [{ type: 'phone', value: '+79130000000' }],
  });

  // Filler dorm rooms with random answers, so the list has a second page.
  const buildings = ['1', '2', '3', '6', '9', '10'];
  for (let i = 0; i < 10; i += 1) {
    const capacity = 2 + pick(3);
    const occupied = 1 + pick(capacity - 1);
    const residents = [];
    for (let r = 1; r < occupied; r += 1) residents.push(person(`Жилец ${i + 1}.${r}`));
    listing(100 + i, person(`Студент ${i + 1}`), residents, {
      kind: 'dorm', building: buildings[i % buildings.length], room_number: 100 + pick(500), floor: 1 + pick(9),
      capacity, occupied_count: occupied,
    });
  }

  // Hidden on purpose: no free places, and a listing that wasn't confirmed.
  listing(200, person('Полная комната'), [person('Сосед')], {
    kind: 'dorm', building: '7', room_number: 101, floor: 1, capacity: 2, occupied_count: 2, status: 'paused',
  });
  listing(201, person('Забытая карточка'), [], {
    kind: 'dorm', building: '7', room_number: 102, floor: 1, capacity: 2, occupied_count: 1, confirmedDaysAgo: 45,
  });

  return db;
}
