from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.auth import exceptions, schemas, service
from th2rag.dependencies import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/token", response_model=schemas.Token, status_code=status.HTTP_200_OK)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db), response: Response = Response()):
    # Dummy example — replace with real auth
    # if form_data.username != "farid.azouaou@thaink2.com" or form_data.password != "secret":
    #     return {"error": "invalid credentials"}
    request = schemas.LoginRequest(email=form_data.username, password=form_data.password)
    try:
        return await service.login(request, response, db)
    except exceptions.InvalidCredentials as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )


# @router.post("/login", response_model=schemas.Token, status_code=status.HTTP_200_OK)
# async def login(
#     request: schemas.LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
# ):
#     try:
#         return await service.login(request, response, db)
#     except exceptions.InvalidCredentials as e:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

#     except UserNotFoundException as e:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/refresh-token", response_model=schemas.Token, status_code=status.HTTP_200_OK)
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        return await service.refresh(request, db)
    except exceptions.InvalidCredentials as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
