# این اسکریپت رو فقط یک‌بار، دستی، بعد از دیپلوی کدِ نقشه‌ی جدید اجرا کن — از ریشه‌ی
# backend با: python -m scripts.reset_map_castles
#
# کاری که می‌کنه: همه‌ی پین‌های قلعه‌ی قبلی رو از map_castles پاک می‌کنه (چون نقشه‌ی
# جدید کاملاً جای قبلی رو گرفته و پین‌های قدیمی دیگه معنی ندارن — باید از نو، دستی از
# پنل ادمین (تب نقشه) برای هر قلعه‌ی جدید پین بذاری). به‌علاوه بازیکن‌هایی که الان به
# قلعه‌ای تخصیص دارن که در نقشه‌ی جدید وجود نداره رو فقط گزارش می‌کنه (چیزی از
# پروفایلشون پاک نمی‌کنه) تا از پنل ادمین دوباره قلعه‌ی جدید بهشون بدی.
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import map_castles, players, game_settings
from game_data import REGIONS


def all_new_castle_names():
    names = set()
    for region in REGIONS.values():
        names.update(region["castles"])
        names.update(region["ports"])
    return names


async def main():
    new_names = all_new_castle_names()

    deleted = await map_castles.delete_many({})
    print(f"پاک شد: {deleted.deleted_count} پینِ قلعه از map_castles")

    await game_settings.delete_one({"_id": "north_map_castles_seeded"})

    orphaned = []
    async for p in players.find({"castle": {"$exists": True, "$ne": None}}, {"tg_id": 1, "name": 1, "castle": 1}):
        if p.get("castle") and p["castle"] not in new_names:
            orphaned.append(p)

    if orphaned:
        print(f"\n{len(orphaned)} بازیکن به قلعه‌ای تخصیص دارن که در نقشه‌ی جدید نیست (باید از پنل ادمین دوباره تخصیص بدی):")
        for p in orphaned:
            print(f"  - {p.get('name')} (tg_id={p['tg_id']}): {p['castle']}")
    else:
        print("\nهیچ بازیکنی به قلعه‌ی حذف‌شده تخصیص نداره.")


if __name__ == "__main__":
    asyncio.run(main())
