from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from database import SessionLocal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import models
from models import (
    ROOM_STATUS,
    AuditLogs,
    Payments,
    Reservation,
    Roles,
    RoomCategories,
    Rooms,
    Users,
)
from pydantic import BaseModel, EmailStr, Field
from router.auth import get_current_user, get_db
from sqlalchemy.orm import Session, aliased

# Pydantic Schemas
class RoomCategory(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    price_per_night: float = Field(gt=0)
    max_occupancy: int = Field(gt=0)

class UpdateRoomCategory(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    price_per_night: Optional[float] = Field(default=None, gt=0)
    max_occupancy: Optional[int] = Field(default=None, gt=0)

class UpdateRoomStatus(BaseModel):
    status: Optional[str] = Field(default=None, min_length=1, max_length=55)
    description: Optional[str] = None

class RoomStatus(BaseModel):
    status: str = Field(min_length=1, max_length=55)
    description: Optional[str] = Field(default=None)

class AddRoom(BaseModel):
    category_id: int = Field(gt=0)
    room_number: str = Field(min_length=1, max_length=20)
    floor: int = Field(ge=0)
    status: int = Field(gt=0)
    is_active: Optional[bool] = Field(default=True)

class UpdateRoom(BaseModel):
    category_id: Optional[Annotated[int, Field(gt=0)]] = None
    room_number: Optional[Annotated[str, Field(min_length=1, max_length=20)]] = None
    floor: Optional[Annotated[int, Field(ge=0)]] = None
    status: Optional[Annotated[int, Field(gt=0)]] = None
    is_active: Optional[bool] = None

class MakePayment(BaseModel):
    reservation_id: int = Field(gt=0)
    amount: float = Field(gt=0)
    payment_method: str = Field(min_length=1, max_length=50)
    payment_status: str = Field(min_length=1, max_length=50)
    transaction_reference: Optional[str] = Field(default=None, max_length=255)
    collected_by: Optional[int] = Field(default=None)
    paid_at: Optional[datetime] = Field(default=None)

class RoomStatusId(BaseModel):
    id: int

# Router Initialization & Dependencies
router = APIRouter()
db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

# Endpoints
@router.post("/admin/create-room-category")
def createRoomCategory(db: db_dependency, user: user_dependency, roomcategory: RoomCategory):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=401, detail="Unauthorized")

    dbuser = db.query(Users).filter(Users.id == user.get("id"), Users.role_id == user.get("role")).first()
    if dbuser is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    category_model = RoomCategories(
        name=roomcategory.name,
        description=roomcategory.description,
        price_per_night=roomcategory.price_per_night,
        max_occupancy=roomcategory.max_occupancy,
    )
    db.add(category_model)
    db.commit()
    return JSONResponse(status_code=201, content={"message": "Room Category Added Successfully"})


@router.put("/admin/update-room-category/{category_id}")
def updateRoomCategory(category_id: int, db: db_dependency, user: user_dependency, roomcategory: UpdateRoomCategory):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=401, detail="Unauthorized")

    dbuser = db.query(Users).filter(
        Users.id == user.get("id"),
        Users.role_id == user.get("role"),
    ).first()

    if dbuser is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    category_model = db.query(RoomCategories).filter(
        RoomCategories.id == category_id
    ).first()

    if category_model is None:
        raise HTTPException(status_code=404, detail="Room Category not found")

    update_data = roomcategory.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    if "name" in update_data:
        duplicate = db.query(RoomCategories).filter(
            RoomCategories.name == update_data["name"],
            RoomCategories.id != category_id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Room Category name already exists")

    for field, value in update_data.items():
        setattr(category_model, field, value)

    db.commit()
    return JSONResponse(status_code=200, content={"message": "Room Category Updated Successfully"})


@router.post("/admin/create-room-status")
def createRoomStatus(db: db_dependency, user: user_dependency, roomstatus: RoomStatus):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=401, detail="Unauthorized")

    dbuser = db.query(Users).filter(
        Users.id == user.get("id"), Users.role_id == user.get("role")
    ).first()

    if dbuser is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    status_model = ROOM_STATUS(status=roomstatus.status, description=roomstatus.description)

    db.add(status_model)
    db.commit()

    return JSONResponse(status_code=201, content={"message": "Room Status Added Successfully"})


@router.put("/admin/update-room-status-definition/{status_id}")
def updateRoomStatus(
    status_id: int,
    db: db_dependency,
    user: user_dependency,
    roomstatus: UpdateRoomStatus,
):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=401, detail="Unauthorized")

    dbuser = db.query(Users).filter(
        Users.id == user.get("id"),
        Users.role_id == user.get("role"),
    ).first()

    if dbuser is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    status_model = db.query(ROOM_STATUS).filter(
        ROOM_STATUS.id == status_id
    ).first()

    if status_model is None:
        raise HTTPException(status_code=404, detail="Room Status not found")

    update_data = roomstatus.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided to update",
        )

    if "status" in update_data:
        duplicate = db.query(ROOM_STATUS).filter(
            ROOM_STATUS.status == update_data["status"],
            ROOM_STATUS.id != status_id,
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="Room Status already exists",
            )

    for field, value in update_data.items():
        setattr(status_model, field, value)

    db.commit()

    return JSONResponse(
        status_code=200,
        content={"message": "Room Status Updated Successfully"},
    )


@router.get("/admin/specific-room-status/{status_id}")
def specificRoomStatus(user: user_dependency, db: db_dependency, status_id: int):
    if user is None:
        raise HTTPException(status_code=401, detail="Please Login First")

    if user.get("role") != 1:
        raise HTTPException(status_code=403, detail="Unauthorized")

    dbuser = db.query(Users).filter(
        Users.id == user.get("id"),
        Users.role_id == user.get("role"),
    ).first()

    if dbuser is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    room_status = db.query(ROOM_STATUS).filter(
        ROOM_STATUS.id == status_id
    ).first()

    if room_status is None:
        raise HTTPException(status_code=404, detail="Room Status not found")

    return room_status


@router.delete("/admin/delete-room/{room_id}")
def deleteRoom(user: user_dependency, db: db_dependency, room_id: int):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=403, detail="Forbidden")

    room = db.query(Rooms).filter(Rooms.id == room_id).first()
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    room_number = room.room_number
    room.is_active = False
    room.status = 6
    db.commit()

    return {"message": f"{room_number} has been deleted"}


@router.put("/admin/update-room/{room_id}")
def update(user: user_dependency, db: db_dependency, updroom: UpdateRoom, room_id: int):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=403, detail="Forbidden")

    room = db.query(Rooms).filter(Rooms.id == room_id).first()

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    for key, value in updroom.model_dump(exclude_unset=True).items():
        setattr(room, key, value)

    db.commit()
    db.refresh(room)

    return {"message": f"{room.room_number} has been updated"}


@router.get("/admin/room-status")
def allRoomStatus(db: db_dependency, user: user_dependency):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=401, detail="Unauthorized")

    room_status = db.query(ROOM_STATUS).all()
    return room_status


@router.post("/admin/create-room")
def createRoom(db: db_dependency, user: user_dependency, room: AddRoom):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=401, detail="Unauthorized")

    dbuser = db.query(Users).filter(
        Users.id == user.get("id"), Users.role_id == user.get("role")
    ).first()

    if dbuser is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    room_model = Rooms(
        category_id=room.category_id,
        room_number=room.room_number,
        floor=room.floor,
        status=room.status,
        is_active=room.is_active,
    )

    db.add(room_model)
    db.commit()
    db.refresh(room_model)

    return JSONResponse(status_code=201, content={"message": "Room Added Successfully"})


@router.put("/admin/update-room-status/{room_id}")
def updateSpecificRoomStatus(
    db: db_dependency,
    user: user_dependency,
    room_id: int,
    status_id: RoomStatusId,
):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=401, detail="Unauthorized")

    room = db.query(Rooms).filter(Rooms.id == room_id).first()

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    status = db.query(ROOM_STATUS).filter(
        ROOM_STATUS.id == status_id.id
    ).first()

    if status is None:
        raise HTTPException(status_code=404, detail="Room status not found")

    room.status = status.id

    db.commit()
    db.refresh(room)

    return JSONResponse(status_code=200, content={"message": f"Room {room.room_number} status updated successfully"})


@router.post("/admin/create-payment")
def createPayment(db: db_dependency, user: user_dependency, payment: MakePayment):
    if user is None or user.get("role") != 1:
        raise HTTPException(status_code=401, detail="Unauthorized")

    dbuser = db.query(Users).filter(Users.id == user.get("id"), Users.role_id == user.get("role")).first()

    if dbuser is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    payment_model = Payments(
        reservation_id=payment.reservation_id,
        amount=payment.amount,
        payment_method=payment.payment_method,
        payment_status=payment.payment_status,
        transaction_reference=payment.transaction_reference,
        collected_by=payment.collected_by,
        paid_at=payment.paid_at,
    )

    db.add(payment_model)
    db.commit()

    return JSONResponse(status_code=201, content={"message": "Payment Added Successfully"})