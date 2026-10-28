"""Admin: change an account's plan (billing is manual during pilots).

python -m scripts.set_plan someone@brand.com growth
"""

import argparse

from sqlalchemy import select

from app.core.config import Settings
from app.platform.db import Database
from app.platform.models import User
from app.platform.plans import PLANS


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("plan", choices=list(PLANS))
    a = ap.parse_args(argv)
    db = Database(Settings().database_url)
    with db.sessionmaker() as s:
        user = s.scalar(select(User).where(User.email == a.email.lower()))
        if user is None:
            raise SystemExit(f"No user with email {a.email}")
        user.org.plan = a.plan
        s.commit()
        print(f"{user.org.name}: plan set to {a.plan}")


if __name__ == "__main__":
    main()
