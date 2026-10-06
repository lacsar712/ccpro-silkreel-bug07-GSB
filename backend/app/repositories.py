from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Basin, BathReading, Filature, User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()


class BasinRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def board(self) -> Filature | None:
        result = await self.session.execute(
            select(Filature).options(
                selectinload(Filature.basins).selectinload(Basin.readings)
            )
        )
        return result.scalars().first()

    async def get(self, basin_id: int) -> Basin | None:
        result = await self.session.execute(
            select(Basin)
            .options(selectinload(Basin.readings))
            .where(Basin.id == basin_id)
        )
        return result.scalar_one_or_none()

    async def add_reading(self, basin: Basin, temp_c: float, operator: str) -> BathReading:
        row = BathReading(basin=basin, water_temp_c=temp_c, operator=operator)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def save_status(self, basin: Basin, status: str) -> None:
        basin.status = status
        await self.session.commit()

    async def void_reading(self, reading_id: int) -> int | None:
        """作废单条汤温。

        条件删除只命中 id 对应的那一行；同一条被两名工并发作废时，
        数据库行锁保证只有一条 DELETE 能删到（rowcount == 1），另一条
        删 0 行返回 None，调用方据此整笔退回。绝不触碰同盆其它行。
        返回被删行所属盆 id；记录不存在时返回 None。
        """
        result = await self.session.execute(
            delete(BathReading)
            .where(BathReading.id == reading_id)
            .returning(BathReading.basin_id)
        )
        basin_id = result.scalar_one_or_none()
        if basin_id is None:
            await self.session.rollback()
            return None
        await self.session.commit()
        return basin_id
