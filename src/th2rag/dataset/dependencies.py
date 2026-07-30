from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.database import get_db
from th2rag.dataset import exceptions, schemas, service
from th2rag.dependencies import get_current_user
from th2rag.users.schemas import User


async def get_dataset_or_404(
    dataset_id: int = Path(...), db: AsyncSession = Depends(get_db)
) -> schemas.Dataset:
    try:
        return await service.get_dataset_by_id(dataset_id, db)
    except exceptions.DatasetNotFoundException:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Dataset not found")


async def require_dataset_owner_or_admin(
    dataset: schemas.Dataset = Depends(get_dataset_or_404),
    current_user: User = Depends(get_current_user),
) -> schemas.Dataset:
    if current_user.role != "ADMIN" and dataset.user_id != current_user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return dataset
