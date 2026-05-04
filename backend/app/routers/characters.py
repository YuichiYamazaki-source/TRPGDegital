from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.database import get_db
from app.models.character import Character
from app.schemas.character import CharacterCreate, CharacterResponse

router = APIRouter()


@router.get("/", response_model=list[CharacterResponse])
async def list_characters(session_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Character)
    if session_id:
        q = q.where(Character.session_id == session_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=CharacterResponse, status_code=201)
async def create_character(body: CharacterCreate, db: AsyncSession = Depends(get_db)):
    character = Character(**body.model_dump())
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(character_id: UUID, body: CharacterCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    for key, value in body.model_dump().items():
        setattr(character, key, value)
    await db.commit()
    await db.refresh(character)
    return character
