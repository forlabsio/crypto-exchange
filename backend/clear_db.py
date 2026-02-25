import asyncio
from app.database import AsyncSessionLocal
from app.models import User, Wallet, Order, Transaction, Bot
from sqlalchemy import delete

async def clear_all_data():
    async with AsyncSessionLocal() as session:
        # Delete in correct order (respecting foreign keys)
        await session.execute(delete(Transaction))
        await session.execute(delete(Order))
        await session.execute(delete(Bot))
        await session.execute(delete(Wallet))
        await session.execute(delete(User))
        await session.commit()
        print("✅ All user data deleted!")

asyncio.run(clear_all_data())
