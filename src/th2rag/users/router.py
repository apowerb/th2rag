from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from th2rag.database import get_db
from th2rag.dependencies import get_admin_user, get_current_user
from th2rag.pagination import PageParams, PageResponse
from th2rag.users import dependencies, exceptions, schemas, service
from th2rag.users.schemas import UserLLMConfigCreate, UserLLMConfigRead


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=PageResponse[schemas.User], dependencies=[Depends(get_admin_user)])
async def get_all_users(page_params: PageParams = Depends(), db: AsyncSession = Depends(get_db)):
    return await service.get_all_users(page_params, db)


@router.post("/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await service.create_user(user_in, db)
    except exceptions.EmailAlreadyExists as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_user_route(user: schemas.User = Depends(get_current_user)):
    return user


@router.get("/{user_id}", response_model=schemas.User)
async def get_user_by_id(user: schemas.User = Depends(dependencies.require_user_owner_or_admin)):
    return user


@router.get("/email/{user_email}", response_model=schemas.User)
async def get_user_by_email(
    user: schemas.User = Depends(dependencies.require_user_owner_or_admin_by_email),
):
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user: schemas.User = Depends(dependencies.require_user_owner_or_admin), db=Depends(get_db)
):
    await service.delete_user_by_id(user.user_id, db)


@router.delete("/email/{user_email}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_email(
    user: schemas.User = Depends(dependencies.require_user_owner_or_admin_by_email),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_user_by_id(user.user_id, db)


@router.post("/{user_id}/llm-config", response_model=UserLLMConfigRead, status_code=status.HTTP_201_CREATED)
async def create_or_update_llm_config(
    user_id: int,
    config: UserLLMConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create or update user's LLM configuration"""
    result = await service.create_or_update_llm_config(user_id, config, db)
    return result


@router.get("/{user_id}/llm-config", response_model=UserLLMConfigRead)
async def get_llm_config(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get user's LLM configuration (API key not returned)"""
    config = await service.get_llm_config(user_id, db)
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not found")
    return config


@router.delete("/{user_id}/llm-config", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete user's LLM configuration"""
    deleted = await service.delete_llm_config(user_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="LLM config not found")
