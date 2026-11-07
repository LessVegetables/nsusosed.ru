"""Sample data for local development: about 20 homes with residents and answers.

    EMAIL_MODE=log python -m app.seed           # fill an empty database
    EMAIL_MODE=log python -m app.seed --reset   # wipe every table first, then fill

Refuses to run unless EMAIL_MODE=log, so it can't touch production by accident.
Deterministic: the same homes every time. Log in as any @g.nsu.ru address (the
code appears in the backend log), or as one of the residents: student1@g.nsu.ru …
Demo invite link: {PUBLIC_ORIGIN}/join#token=demo-invite-token (Аня's room).
"""

from __future__ import annotations
import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select, text
from app.config import QUESTIONNAIRE, settings
from app.database import async_session_factory, engine
from app.models import Listing, ListingContact, Membership, Profile, User
from app.utils.security import sha256_hex

DEMO_INVITE_TOKEN = "demo-invite-token"
TABLES = ["auth_events", "otp_codes", "sessions", "memberships", "listing_contacts", "listing_photos",
          "listings", "profiles", "users"]

EARLY = {"sleep": 1, "wake": 1, "noise": 0, "cleanliness": 3, "guests": 1, "smoking": 0, "alcohol": 0,
         "study": 3, "airing": 2, "temperature": 2}
OWL = {"sleep": 4, "wake": 4, "noise": 3, "cleanliness": 1, "guests": 3, "smoking": 0, "alcohol": 2,
       "study": 1, "airing": 1, "temperature": 3}


class Seeder:
    def __init__(self, db):
        self.db = db
        self.rnd = random.Random(42)
        self.now = datetime.now(timezone.utc)
        self.n = 0

    def days_ago(self, days: float) -> datetime:
        return self.now - timedelta(days=days)

    def person(self, name: str, values: dict | None = None, hard: dict | None = None, *,
               profile: bool = True) -> User:
        """A resident. Answers not given in `values` are random; `hard` is {question: allowed values}."""
        values, hard = values or {}, hard or {}
        self.n += 1
        user = User(email=f"student{self.n}@g.nsu.ru", display_name=name, language="ru",
                    privacy_accepted_at=self.days_ago(40))
        self.db.add(user)
        if profile:
            answers = {}
            for q in QUESTIONNAIRE["questions"]:
                key = q["key"]
                answers[key] = {
                    "value": values.get(key, self.rnd.randint(q["min_value"], q["max_value"])),
                    "importance": self.rnd.randint(3, 10),
                    "hard": key in hard,
                    "allowed": hard.get(key, []),
                }
            user.profile = Profile(questionnaire_version=QUESTIONNAIRE["version"], answers=answers,
                                   situation="host", version=1)
        return user

    def home(self, admin: User, residents: list[User], *, contacts: list[tuple[str, str]] | None = None,
             confirmed_days_ago: float = 2, invite_token: str | None = None, **fields) -> Listing:
        """A home; `admin` is its admin, everyone else a plain resident."""
        listing = Listing(status=fields.pop("status", "active"), version=1,
                          confirmed_at=self.days_ago(confirmed_days_ago), **fields)
        listing.contacts = [ListingContact(position=i, type=t, value=v)
                            for i, (t, v) in enumerate(contacts or [("telegram", "nsu_student")])]
        if invite_token:
            listing.invite_token_hash = sha256_hex(invite_token)
            listing.invite_expires_at = self.now + timedelta(days=settings.invite_ttl_days)
        listing.memberships = [Membership(user=u, is_admin=(i == 0), joined_at=self.days_ago(40 - i))
                               for i, u in enumerate([admin, *residents])]
        self.db.add(listing)
        return listing

    def fill(self) -> None:
        p = self.person
        self.home(p("Аня", EARLY), [p("Катя", EARLY | {"sleep": 2})],
                  kind="dorm", building="7", room_number=214, floor=2, capacity=4, occupied_count=3,
                  is_corner=True, windows_count=2, view="forest", layout="Блок на две комнаты, душ в блоке",
                  description="Тихая комната, рано ложимся. Третья соседка заселится в сентябре.",
                  contacts=[("telegram", "anya_nsu"), ("phone", "+79131112233")], invite_token=DEMO_INVITE_TOKEN)
        self.home(p("Дима", OWL), [p("Саша", OWL | {"guests": 4}), p("Миша", profile=False)],
                  kind="dorm", building="10А", room_number=512, floor=5, capacity=4, occupied_count=3,
                  view="road", description="Сова-friendly: ложимся поздно, по выходным бывают гости.",
                  contacts=[("phone", "+79991234567")])
        self.home(p("Лена", EARLY | {"sleep": 0}), [p("Оля", OWL | {"sleep": 4})],
                  kind="dorm", building="5", room_number=302, floor=3, capacity=3, occupied_count=2,
                  windows_count=1, view="yard", contacts=[("whatsapp", "+79137654321")])
        self.home(p("Рома", {"smoking": 1}, {"smoking": [1]}), [],
                  kind="dorm", building="8", room_number=122, floor=1, capacity=2, occupied_count=1,
                  description="Курю на балконе, ищу соседа, которого это не смущает.",
                  contacts=[("max", "roma.max")])
        self.home(p("Ира", EARLY), [], confirmed_days_ago=27,
                  kind="dorm", building="4", room_number=401, floor=4, capacity=2, occupied_count=1,
                  contacts=[("other", "vk.com/ira_nsu")])
        self.home(p("Женя", EARLY), [p("Паша")],
                  kind="apartment", district="Верхняя зона", monthly_cost_per_person_rub=15000,
                  capacity=3, occupied_count=2, description="Трёшка у Морского проспекта, одна комната свободна.",
                  contacts=[("telegram", "zhenya_flat")])
        self.home(p("Вика", OWL), [],
                  kind="apartment", district="Щ", monthly_cost_per_person_rub=25000, capacity=2, occupied_count=1,
                  contacts=[("telegram", "vika_shch")])
        self.home(p("Гоша"), [p("Лёша")],
                  kind="apartment", district="Шлюз", monthly_cost_per_person_rub=12000, capacity=4,
                  occupied_count=2, contacts=[("phone", "+79130000000")])

        # Filler dorm rooms with random answers, so the list has a second page.
        buildings = ["1", "2", "3", "6", "9", "10"]
        rooms = self.rnd.sample(range(100, 600), 10)
        for i in range(10):
            capacity = self.rnd.randint(2, 4)
            occupied = self.rnd.randint(1, capacity - 1)
            residents = [p(f"Жилец {i + 1}.{r}") for r in range(1, occupied)]
            self.home(p(f"Студент {i + 1}"), residents, kind="dorm", building=buildings[i % len(buildings)],
                      room_number=rooms[i], floor=self.rnd.randint(1, 9), capacity=capacity, occupied_count=occupied)

        # Hidden on purpose: no free places, and a listing nobody confirmed for 45 days.
        self.home(p("Полная комната"), [p("Сосед")], status="paused",
                  kind="dorm", building="7", room_number=101, floor=1, capacity=2, occupied_count=2)
        self.home(p("Забытая карточка"), [], confirmed_days_ago=45,
                  kind="dorm", building="7", room_number=102, floor=1, capacity=2, occupied_count=1)


async def main(reset: bool) -> int:
    if settings.email_mode != "log":
        print("Refusing to seed: set EMAIL_MODE=log (seeding is for local development only).", file=sys.stderr)
        return 1
    async with async_session_factory() as db:
        if reset:
            await db.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
        elif (await db.execute(select(func.count()).select_from(User))).scalar():
            print("The database already has users. Use --reset to wipe it first.", file=sys.stderr)
            return 1
        seeder = Seeder(db)
        seeder.fill()
        await db.commit()
        homes = (await db.execute(select(func.count()).select_from(Listing))).scalar()
    await engine.dispose()
    print(f"Seeded {seeder.n} residents in {homes} homes.")
    print(f"Demo invite: {settings.public_origin}/join#token={DEMO_INVITE_TOKEN}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="wipe every table first")
    sys.exit(asyncio.run(main(parser.parse_args().reset)))
