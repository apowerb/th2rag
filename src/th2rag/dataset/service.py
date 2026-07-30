from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.dataset import exceptions, schemas
from th2rag.models import Dataset
from th2rag.pagination import PageParams, PageResponse, paginate
from th2rag.users.schemas import User


async def get_all_datasets(
    page_params: PageParams, current_user: User, db: AsyncSession
) -> PageResponse[schemas.Dataset]:
    stmt = select(Dataset)
    if current_user.role != "ADMIN":
        stmt = stmt.where(Dataset.user_id == current_user.user_id)
    return await paginate(db, stmt, page_params, schemas.Dataset)


async def create_dataset(
    dataset_in: schemas.DatasetCreate, user_id: int, db: AsyncSession
) -> schemas.Dataset:
    new_dataset = Dataset(
        name=dataset_in.name,
        n_columns=dataset_in.n_columns,
        n_rows=dataset_in.n_rows,
        column_types=dataset_in.column_types,
        user_id=user_id,
    )

    db.add(new_dataset)
    await db.commit()
    await db.refresh(new_dataset)

    return schemas.Dataset.model_validate(new_dataset)


async def get_dataset_by_id(dataset_id: int, db: AsyncSession) -> schemas.Dataset:
    stmt = select(Dataset).where(Dataset.dataset_id == dataset_id)
    result = await db.execute(stmt)
    dataset = result.scalar_one_or_none()

    if not dataset:
        raise exceptions.DatasetNotFoundException("Dataset not found")

    return schemas.Dataset.model_validate(dataset)


async def update_dataset(
    dataset_id: int, dataset_in: schemas.DatasetCreate, db: AsyncSession
) -> schemas.Dataset:
    stmt = select(Dataset).where(Dataset.dataset_id == dataset_id)
    result = await db.execute(stmt)
    dataset = result.scalar_one_or_none()

    if not dataset:
        raise exceptions.DatasetNotFoundException("Dataset not found")

    dataset.name = dataset_in.name
    dataset.n_columns = dataset_in.n_columns
    dataset.n_rows = dataset_in.n_rows
    dataset.column_types = dataset_in.column_types

    await db.commit()
    await db.refresh(dataset)

    return schemas.Dataset.model_validate(dataset)


async def delete_dataset(dataset_id: int, db: AsyncSession) -> None:
    stmt = select(Dataset).where(Dataset.dataset_id == dataset_id)
    result = await db.execute(stmt)
    dataset = result.scalar_one_or_none()

    if not dataset:
        raise exceptions.DatasetNotFoundException("Dataset not found")

    await db.delete(dataset)
    await db.commit()
