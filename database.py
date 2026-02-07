import aiosqlite

async def create_db():
    async with aiosqlite.connect("dating_bot.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                age INTEGER,
                city TEXT,
                photo_id TEXT,
                description TEXT
            )
        """)
        await db.commit()
