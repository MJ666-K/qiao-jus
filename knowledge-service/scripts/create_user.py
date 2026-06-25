"""Create a user directly in the database (bypasses HTTP captcha). For deploy bootstrap.

Usage (inside api container):
  python -m scripts.create_user
  python -m scripts.create_user --email admin@example.com --password 'yourpass8' --role admin
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from core.security import hash_password
from models.base import Tenant, User
from storage.postgres import SessionLocal


async def main() -> int:
    parser = argparse.ArgumentParser(description="Create initial user for production bootstrap")
    parser.add_argument("--email", default="seed@demo.com")
    parser.add_argument("--password", default="seed12345")
    parser.add_argument("--role", default="admin", choices=["user", "admin"])
    parser.add_argument("--tenant", default="default")
    parser.add_argument("--display-name", default="seed")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("ERROR: password must be at least 8 characters", file=sys.stderr)
        return 1

    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.email == args.email))
        if res.scalars().first():
            print(f"用户已存在，跳过: {args.email}")
            return 0

        tenant = Tenant(name=args.tenant)
        session.add(tenant)
        await session.flush()

        user = User(
            tenant_id=tenant.id,
            email=args.email,
            password_hash=hash_password(args.password),
            role=args.role,
            display_name=args.display_name,
            scopes=["read", "write"],
        )
        session.add(user)
        await session.commit()
        print(f"✔ 已创建用户 {args.email} (role={args.role}, tenant={args.tenant})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
