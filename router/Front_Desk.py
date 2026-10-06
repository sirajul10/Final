from datetime import datetime, timezone
from typing import Annotated, Optional

from database import SessionLocal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
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
from pydantic import BaseModel, Field
from router.auth import get_current_user, get_db
from sqlalchemy.orm import Session

router = APIRouter()
db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


@router.put("/front-desk/check-in/{reservation_id}")
def checkIn(db: db_dependency, user: user_dependency, reservation_id: int):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()

    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation Not Found")

    if reservation.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot check in a cancelled reservation")

    if reservation.status == "checked_in":
        raise HTTPException(status_code=400, detail="Guest is already checked in")

    if reservation.room_id is None:
        raise HTTPException(status_code=400, detail="No room assigned to this reservation")

    room = db.query(Rooms).filter(Rooms.id == reservation.room_id).first()

    if room is None:
        raise HTTPException(status_code=404, detail="Room Not Found")

    if room.status != 1:
        raise HTTPException(status_code=400, detail="Room is not available")

    reservation.status = "checked_in"
    reservation.updated_at = datetime.now(timezone.utc)
    room.status = 2

    db.commit()

    return {
        "message": "Guest Checked In Successfully",
        "reservation_id": reservation.id,
        "room_id": reservation.room_id,
        "status": reservation.status,
    }


@router.put("/front-desk/check-out/{reservation_id}")
def check_out(db: db_dependency, user: user_dependency, reservation_id: int):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if reservation.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot check out a cancelled reservation")

    if reservation.status == "checked_out":
        raise HTTPException(status_code=400, detail="Guest is already checked out")

    if reservation.status != "checked_in":
        raise HTTPException(status_code=400, detail="Guest must be checked in before checking out")

    if reservation.room_id is None:
        raise HTTPException(status_code=400, detail="No room assigned to this reservation")

    room = db.query(Rooms).filter(Rooms.id == reservation.room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    reservation.status = "checked_out"
    reservation.updated_at = datetime.now(timezone.utc)
    room.status = 1  # 1 represents Available status
    db.commit()

    return {
        "message": "Guest checked out successfully",
        "reservation_id": reservation.id,
        "room_id": reservation.room_id,
        "status": reservation.status,
    }


@router.get("/front-desk/dashboard")
def dashboard(db: db_dependency, user: user_dependency):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    total_reservations = db.query(Reservation).count()
    checked_in = db.query(Reservation).filter(Reservation.status == "checked_in").count()
    checked_out = db.query(Reservation).filter(Reservation.status == "checked_out").count()
    cancelled = db.query(Reservation).filter(Reservation.status == "cancelled").count()

    return {
        "total_reservations": total_reservations,
        "checked_in": checked_in,
        "checked_out": checked_out,
        "cancelled": cancelled,
    }


@router.get("/front-desk/reservations")
def get_reservations(db: db_dependency, user: user_dependency, page: int = 1, page_size: int = 10):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be greater than 0")

    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="Page size must be between 1 and 100")

    total = db.query(Reservation).count()
    reservations = db.query(Reservation).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "reservations": reservations,
    }


@router.get("/front-desk/reservations/{reservation_id}")
def get_reservation(db: db_dependency, user: user_dependency, reservation_id: int):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    return reservation


@router.put("/front-desk/reservations/{reservation_id}/assign-room/{room_id}")
def assign_room(db: db_dependency, user: user_dependency, reservation_id: int, room_id: int):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if reservation.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot assign room to a cancelled reservation")

    room = db.query(Rooms).filter(Rooms.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.status != 1:
        raise HTTPException(status_code=400, detail="Room is not available")

    reservation.room_id = room.id
    reservation.updated_at = datetime.now(timezone.utc)

    db.commit()

    return {"message": "Room assigned successfully", "reservation_id": reservation.id, "room_id": room.id}


@router.put("/front-desk/reservations/{reservation_id}/change-room/{new_room_id}")
def change_room(db: db_dependency, user: user_dependency, reservation_id: int, new_room_id: int):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if reservation.status not in ["reserved", "confirmed", "checked_in"]:
        raise HTTPException(status_code=400, detail="Room cannot be changed for this reservation")

    if reservation.room_id == new_room_id:
        raise HTTPException(status_code=400, detail="Guest is already assigned to this room")

    new_room = db.query(Rooms).filter(Rooms.id == new_room_id).first()

    if not new_room:
        raise HTTPException(status_code=404, detail="New room not found")

    if new_room.status != 1:
        raise HTTPException(status_code=400, detail="New room is not available")

    old_room = None
    if reservation.room_id:
        old_room = db.query(Rooms).filter(Rooms.id == reservation.room_id).first()

    reservation.room_id = new_room.id
    reservation.updated_at = datetime.now(timezone.utc)
    new_room.status = 2  # 2 represents Occupied status

    if old_room:
        old_room.status = 1  # 1 represents Available status

    db.commit()

    return {
        "message": "Room changed successfully",
        "reservation_id": reservation.id,
        "old_room_id": old_room.id if old_room else None,
        "new_room_id": new_room.id,
    }


@router.get("/front-desk/rooms/available")
def get_available_rooms(db: db_dependency, user: user_dependency):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    rooms = db.query(Rooms).filter(Rooms.status == 1).all()
    return rooms


@router.put("/front-desk/rooms/{room_id}/status/{status_id}")
def update_room_status(db: db_dependency, user: user_dependency, room_id: int, status_id: int):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    room = db.query(Rooms).filter(Rooms.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    room.status = status_id

    db.commit()

    return {"message": "Room status updated successfully", "room_id": room.id, "status": room.status}


@router.get("/front-desk/guests/search/{name}")
def search_guest(name: str, db: db_dependency, user: user_dependency):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    users = db.query(Users).filter(Users.username.ilike(f"%{name}%")).all()

    if not users:
        raise HTTPException(status_code=404, detail="Guest not found")

    return users


@router.put("/front-desk/reservations/{reservation_id}/cancel")
def cancel_reservation(reservation_id: int, db: db_dependency, user: user_dependency):
    if user is None or user.get("role") == 3:
        raise HTTPException(status_code=401, detail="Unauthorized")

    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if reservation.status == "cancelled":
        raise HTTPException(status_code=400, detail="Reservation is already cancelled")

    if reservation.status == "checked_out":
        raise HTTPException(status_code=400, detail="Cannot cancel a completed reservation")

    reservation.status = "cancelled"
    reservation.cancelled_at = datetime.now(timezone.utc)
    reservation.cancelled_by = user.get("id")
    reservation.updated_at = datetime.now(timezone.utc)

    if reservation.room_id:
        room = db.query(Rooms).filter(Rooms.id == reservation.room_id).first()
        if room and room.status == 2:
            room.status = 1

    db.commit()

    return {"message": "Reservation cancelled successfully", "reservation_id": reservation.id}