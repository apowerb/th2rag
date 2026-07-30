from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.database import get_db
from th2rag.dataset import dependencies, schemas, service
from th2rag.dependencies import get_current_user
from th2rag.pagination import PageParams, PageResponse
from th2rag.users import schemas as user_schemas
from th2rag.users.schemas import User

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/", response_model=PageResponse[schemas.Dataset])
async def get_all_datasets(
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    return await service.get_all_datasets(page_params, current_user, db)


@router.post("/", response_model=schemas.Dataset, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    dataset: schemas.DatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_dataset(dataset, current_user.user_id, db)


@router.put("/{dataset_id}", response_model=schemas.Dataset)
async def update_dataset(
    dataset_update: schemas.DatasetCreate,
    dataset: schemas.Dataset = Depends(dependencies.require_dataset_owner_or_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_dataset(dataset.dataset_id, dataset_update, db)


@router.get("/{dataset_id}", response_model=schemas.Dataset)
async def get_dataset_by_id(
    dataset: schemas.Dataset = Depends(dependencies.require_dataset_owner_or_admin),
):
    return dataset


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset: schemas.Dataset = Depends(dependencies.require_dataset_owner_or_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_dataset(dataset.dataset_id, db)
