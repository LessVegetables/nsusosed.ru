#!/usr/bin/env python3
"""Scratchpad stand-in for the site: serves ./site with clean URLs and a mock /api.
Room ids: flat-5, dorm-1, flat-1p (p = the single photo is a portrait one)."""
import json, mimetypes, re, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "site"
ME = {"user_id": "00000000-0000-0000-0000-000000000001", "first_name": "Даня", "last_name": "Тестов", "email": "d.testov@g.nsu.ru",
      "language": "ru", "home_id": None, "has_questionnaire": True, "gender": "m"}
MINE = dict(A1=1, A2=2, A3=2, A4=0, B2=1, C1=2, C2=0, D1=1, D2=1, E3=1, G1=1, G2=1, G3=1)
SHAPES = ["4x3", "3x4", "4x3", "16x9", "3x4", "4x3", "1x1", "4x3"]

def compat(pct, **badges):
    return {"percent": pct, "badges": badges}

def person(n, first, last, bio, here, answers, c):
    return {"user_id": f"00000000-0000-0000-0000-00000000010{n}", "first_name": first, "last_name": last, "avatar_url": None,
            "bio": bio, "in_this_room": here, "answers": answers, "compatibility": c}

MASHA = person(1, "Маша", "Орлова", "ФИТ, 3 курс. Сова: кодю по ночам, утром меня лучше не трогать. Люблю настолки и готовить на всех.", True,
               dict(A1=4, A2=5, A3=0, A4=2, B2=1, C1=2, C2=2, D1=1, D2=2, E3=1, G1=1, G2=1, G3=1),
               compat(60, sleep="discuss", order="match", quiet="discuss", air="match", living="match"))
ANYA = person(2, "Аня", "Ким", "ФЕН, магистратура. Много времени в лаборатории, дома в основном сплю и читаю.", True,
              dict(A1=1, A2=3, A3=2, A4=0, B2=1, C1=1, C2=0, D1=2, D2=1, E3=1, G1=1, G2=1, G3=2),
              compat(90, sleep="match", order="match", quiet="match", air="match", living="ok"))
LENA = person(3, "Лена", "Соколова", "", False, {}, None)

def room(rid):
    m = re.fullmatch(r"(flat|dorm)-(\d)(p?)", rid)
    if not m:
        return None
    kind, n, portrait = m.group(1), int(m.group(2)), m.group(3)
    order = list(range(8))
    if portrait:
        order = [1] + [i for i in order if i != 1]
    photos = [{"id": f"p{i + 1}", "url": f"/mock/photos/p{i + 1}-{SHAPES[i]}.svg"} for i in order[:n]]
    base = {"room_id": rid, "home_id": "h1", "kind": kind, "building": None, "district": None, "sunlight": "sunny",
            "gender": "any", "rent_rub": None, "utilities_mode": None, "utilities_rub": None, "internet_mode": None,
            "photos": photos, "other_rooms": [], "my_answers": MINE, "is_mine": False, "can_get_contacts": True}
    if kind == "flat":
        base.update(kind="apartment", district="Верхняя зона", lat=54.8437, lon=83.0907, radius_m=350, emoji="🦊🌵🚲",
                    room_name="Большая с балконом", gender="f", capacity=2, free_places=1, rent_rub=14500,
                    utilities_mode="split", utilities_rub=2500, internet_mode="split",
                    description="Трёшка на Морском, 5 этаж из 9, лифт работает. Комната 18 м² с балконом на лес, две кровати, два стола, большой шкаф.\n\nНа кухне есть всё: посудомойка, микроволновка, мультиварка. Стиралка в ванной. До НГУ 15 минут пешком или 2 остановки.\n\nХозяйка спокойная, приходит раз в месяц. Животных нельзя, гостей можно, если предупредить.",
                    residents=[MASHA, ANYA, LENA], compatibility=compat(60, sleep="discuss", order="match", quiet="discuss", air="match", living="ok"),
                    other_rooms=[{"room_id": "flat-3", "emoji": "🐸🎧🍋", "room_name": "Маленькая", "free_places": 1, "rent_rub": 11000},
                                 {"room_id": "flat-2", "emoji": "🦉📚☕", "room_name": "Проходная", "free_places": 0, "rent_rub": 9000}])
    else:
        base.update(building="2", lat=54.84439, lon=83.09405, radius_m=0, emoji="🐙🍉🎸", room_name="", capacity=3, free_places=1,
                    sunlight="partial", description="Третий этаж, окна во двор, тихо. Есть холодильник и чайник, блок на две комнаты. Соседний блок дружный, по пятницам играем в мафию.",
                    residents=[ANYA, MASHA], compatibility=compat(60, sleep="discuss", order="match", quiet="discuss", air="match", living="ok"))
    return base

CONTACTS = {"hosts": [{"first_name": "Маша", "contacts": [{"type": "telegram", "value": "@masha_orlova", "url": "https://t.me/masha_orlova"},
                                                           {"type": "vk", "value": "vk.com/masha.orlova", "url": "https://vk.com/masha.orlova"}]},
                      {"first_name": "Аня", "contacts": [{"type": "telegram", "value": "@anya_kim", "url": "https://t.me/anya_kim"}]}]}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def js(self, obj, code=200):
        self.send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json")
    def api(self, path):
        if path == "/me": return self.js(ME) if "/login" not in (self.headers.get("Referer") or "") else self.js({"error": {"code": "UNAUTHORIZED", "message": "", "fields": {}, "data": {}}}, 401)
        if path == "/meta": return self.send(200, (ROOT / "mock/meta.json").read_bytes(), "application/json")
        if path == "/questionnaire": return self.send(200, (ROOT / "mock/questionnaire.json").read_bytes(), "application/json")
        m = re.fullmatch(r"/rooms/([\w-]+)(/contacts)?", path)
        if m:
            r = room(m.group(1))
            if r: return self.js(CONTACTS if m.group(2) else r)
        self.js({"error": {"code": "NOT_FOUND", "message": "", "fields": {}, "data": {}}}, 404)
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0)); self.do_GET()
    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/"): return self.api(path[4:])
        f = (ROOT / path.lstrip("/")).resolve()
        if path == "/": f = ROOT / "options.html"
        if not f.is_file() and (ROOT / (path.strip("/") + ".html")).is_file(): f = ROOT / (path.strip("/") + ".html")
        if ROOT not in f.parents or not f.is_file(): return self.send(404, b"not found", "text/plain")
        self.send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8090), H).serve_forever()
