from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.database import get_db
from th2rag.dependencies import get_current_user
from th2rag.knowledge import exceptions, schemas, service
from th2rag.users.schemas import User


async def get_knowledge_or_404(
    knowledge_id: int = Path(...), db: AsyncSession = Depends(get_db)
) -> schemas.Knowledge:
    try:
        return await service.get_knowledge_by_id(knowledge_id, db)
    except exceptions.KnowledgeNotFoundException:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge not found")


async def require_knowledge_owner_or_admin(
    knowledge: schemas.Knowledge = Depends(get_knowledge_or_404),
    current_user: User = Depends(get_current_user),
) -> schemas.Knowledge:
    if current_user.role != "ADMIN" and knowledge.user_id != current_user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return knowledge
