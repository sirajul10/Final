from fastapi import FastAPI,Depends,HTTPException
from sqlalchemy.orm import Session,joinedload
import models
from database import engine,SessionLocal,Base
from fastapi.responses import JSONResponse
from router import auth,admin,Front_Desk
from router.auth import get_db,get_current_user
from typing import Annotated,Optional
from models import Users,Reservation,Rooms,RoomCategories
from pydantic import BaseModel,Field
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware



models.Base.metadata.create_all(bind=engine)

class ReservationCreate(BaseModel):
    room_id: int = Field(gt=0)
    check_in_date: datetime
    check_out_date: datetime
    status: str = Field(min_length=1,max_length=50)
    total_amount: float = Field(gt=0)
    special_request: Optional[str] = Field(default=None)

app = FastAPI()
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(Front_Desk.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_dependency = Annotated[Session,Depends(get_db)]
user_dependency = Annotated[dict,Depends(get_current_user)]


@app.get("/")
def home(db:db_dependency,user:user_dependency):
    return "Hi"



@app.get("/all-rooms")
def AllRooms(db:db_dependency):
    rooms = db.query(Rooms).all()
    return rooms




@app.get("/specific-room/{room_id}")
def specificRoom(db:db_dependency,user:user_dependency, room_id:int):
    if user is None:
        raise HTTPException(status_code=404,detail="Please Login First")
    room = db.query(Rooms).filter(Rooms.id == room_id).first();
    return room

@app.get("/all-category")
def AllCategory(db:db_dependency):
    categories = db.query(RoomCategories).all()
    return categories

@app.get("/specific-category/{cat_id}")
def specificCategory(user:user_dependency,db:db_dependency,cat_id:int):
    if user is None:
        raise HTTPException(status_code=404,detail="Please Login First")
    category = db.query(RoomCategories).filter(RoomCategories.id == cat_id).first();
    return category;

@app.post("/create-reservation")
def createReservation(db:db_dependency,user:user_dependency,reservation:ReservationCreate):

    if user is None:
        raise HTTPException(status_code=401,detail="Unauthorized")

    dbuser = db.query(Users).filter(Users.id == user.get("id")).first()

    if dbuser is None:
        raise HTTPException(status_code=401,detail="Unauthorized")

    if reservation.check_out_date <= reservation.check_in_date:
        raise HTTPException(status_code=400,detail="Check-out date must be after check-in date")

    room = db.query(Rooms).filter(Rooms.id == reservation.room_id,Rooms.is_active == True).first()

    if room is None:
        raise HTTPException(status_code=404,detail="Room not found")

    reservation_model = Reservation(
        user_id=user.get("id"),
        room_id=reservation.room_id,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        status=reservation.status,
        total_amount=reservation.total_amount,
        special_request=reservation.special_request
    )

    db.add(reservation_model)
    db.commit()

    return JSONResponse(status_code=201,content={'message':'Reservation Created Successfully'})

@app.post("/cancel-reservation/{reservation_id}")
def cancelReservation(db: db_dependency, user: user_dependency, reservation_id: int):
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    dbuser = db.query(Users).filter(Users.id == user.get("id")).first()

    if dbuser is None:
        raise HTTPException(status_code=404, detail="User not found")

    reservation = db.query(Reservation).filter(Reservation.id == reservation_id, Reservation.user_id == dbuser.id).first()

    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")

    reservation.status = "cancel request"
    db.commit()
    db.refresh(reservation)

    return {"message": "Reservation cancellation requested successfully", "reservation_id": reservation.id, "status": reservation.status}

@app.get("/sorted-rooms")
def sorted_rooms(db: db_dependency, sort_by: str = "id", order: str = "asc"):

    allowed_sort = {
        "id": Rooms.id,
        "status": Rooms.status,
        "category_id": Rooms.category_id
    }

    if sort_by not in allowed_sort: raise HTTPException(status_code=400, detail="Invalid sort field")

    if order not in ["asc", "desc"]: raise HTTPException(status_code=400, detail="Order must be asc or desc")

    if order == "asc":
        rooms = db.query(Rooms).order_by(allowed_sort[sort_by].asc()).all()
    else:
        rooms = db.query(Rooms).order_by(allowed_sort[sort_by].desc()).all()

    return rooms

@app.get("/myreservations")
def MyReservations(db:db_dependency,user:user_dependency):
    if user is None:
        raise HTTPException(status_code=404,detail="PleaseLogin First")
    myr_reservation = db.query(Reservation).filter(Reservation.user_id == user.get('id')).all()
    return myr_reservation