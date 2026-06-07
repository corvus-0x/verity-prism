"""
Seed a demo user for development and portfolio demos.
Run inside Docker: docker-compose exec backend python -m app.seeds.demo_user

Safe to run multiple times — skips creation if the email already exists.
"""

from app.database import SessionLocal
from app.models.user import User
from app.services.auth import hash_password

DEMO_EMAIL = "demo@verityprism.com"
DEMO_PASSWORD = "demo1234"


def seed_demo_user():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if existing:
            print(f"User with email {DEMO_EMAIL} already exists.")
            return

        new_user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD), full_name="Demo User")
        db.add(new_user)
        db.commit()
        print(f"Demo user created successfully: {DEMO_EMAIL}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_user()
