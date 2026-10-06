from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,EmailStr
from typing import Annotated,Optional
import models
from models import Users,Roles
from sqlalchemy.orm import Session
from database import SessionLocal
from passlib.context import CryptContext
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm,OAuth2PasswordBearer
from jose import jwt,JWTError
from datetime import datetime,timezone,timedelta

# classse 
class CreateUser(BaseModel):
    username: Annotated[str, Field(min_length=3, max_length=55)]
    first_name: Annotated[str, Field(min_length=3, max_length=55)]
    last_name: Annotated[str, Field(min_length=3, max_length=55)]
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=255)]
    phone: Annotated[str, Field(min_length=1, max_length=55)]


class UpdateUser(BaseModel):
    username: Optional[Annotated[str, Field(min_length=3, max_length=55)]] = None
    first_name: Optional[Annotated[str, Field(min_length=3, max_length=55)]] = None
    last_name: Optional[Annotated[str, Field(min_length=3, max_length=55)]] = None
    email: Optional[EmailStr] = None
    phone: Optional[Annotated[str, Field(min_length=1, max_length=55)]] = None

class PassworChange(BaseModel):
    current_password: str
    new_password: Annotated[str, Field(min_length=8, max_length=255)]


class Createnewpassword(BaseModel):
    username: Annotated[str, Field(min_length=3, max_length=55)]
    new_password: Annotated[str, Field(min_length=8, max_length=255)]
    email: EmailStr

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter()
bcrypt_context = CryptContext(schemes=['bcrypt'],deprecated = "auto")
oAuth2_bearer = OAuth2PasswordBearer(tokenUrl='login')
SECRET_KEY = "8e484fb160b3165eac1f581dd8b7a873f91920d45e3ff37bdad93523d71427c0"
ALGORITHM = "HS256"


def userAuthenticate(username: str, password: str, db: db_dependency):
    user = db.query(Users).filter(Users.username == username).first()

    if user is None:
        return None

    if bcrypt_context.verify(password, user.password_hash):
        return user

    return None

def createAccessToken(username:str,email:str,userId:int,role:int,expiresTime:timedelta):
    encode = {
        "sub" : username,
        "email" : email,
        "id" : userId,
        "role":role
    }
    endtime = datetime.now(timezone.utc)+expiresTime
    encode.update({'exp':endtime})
    return jwt.encode(
        encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

def get_current_user(token:Annotated[str,Depends(oAuth2_bearer)]):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        username = payload.get('sub')
        email = payload.get('email')
        id = payload.get('id')
        role = payload.get('role')

        if username is None:
            raise HTTPException(status_code=401,detail='Unathenticate User')

        return {
            'username':username,
            'email':email,
            'role':role,
            'id':id
        }

    except JWTError:
        raise HTTPException(status_code=401,detail='Unathenticate User')

db_dependency = Annotated[Session,Depends(get_db)]
user_dependency = Annotated[dict,Depends(get_current_user)]

@router.post("/create-user")
def create_user(db:db_dependency,newuser:CreateUser):
    exisrmail= db.query(Users).filter(Users.email == newuser.email).first()
    exusername = db.query(Users).filter(Users.username == newuser.username).first()
    if exusername is not None:
        raise HTTPException(status_code=409,detail="Username Alrady Exists")
    if exisrmail is not None:
        raise HTTPException(status_code=409,detail="Email Alrady Exists")
    userModel = Users(
        username = newuser.username,
        role_id=3,
        first_name = newuser.first_name,
        last_name = newuser.last_name,
        email = newuser.email,
        password_hash = bcrypt_context.hash(newuser.password),
        phone = newuser.phone
    )
    db.add(userModel)
    db.commit()
    return JSONResponse(status_code=201,content={'message':'User Added Successfull'})


@router.post('/login')
def userlogin(db:db_dependency,form_data:Annotated[OAuth2PasswordRequestForm,Depends()]):
    user = userAuthenticate(form_data.username, form_data.password,db)
    if user is None:
        raise HTTPException(status_code=401,detail="Please Provide valid Login Credintial")
    token = createAccessToken(user.username,user.email,user.id,user.role_id,timedelta(minutes=1440))

    return {
        'access_token':token,
        'token_type':'bearer'
    }


@router.get("/user")
def getUser(db: db_dependency, user: user_dependency):

    current_user = db.query(Users).filter(
        Users.id == user["id"]
    ).first()

    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail="User is not authenticated"
        )

    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role_id": current_user.role_id,
        "is_active": current_user.is_active
    }


@router.get("/role/{role_id}")
def get_user_role(
    role_id: int,
    db: db_dependency,
    user: user_dependency,
):
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if current_user is None:
        raise HTTPException(status_code=401, detail="User is not authenticated")

    role = db.query(Roles).filter(Roles.id == role_id).first()
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")

    return role.name

   

@router.put('/update-user')
def updateUser(db:db_dependency,user:user_dependency,updateuser:UpdateUser):
    if user is None:
        raise HTTPException(status_code=401,detail='User is not authenticate')

    upuser = db.query(Users).filter(Users.id == user.get('id')).first()
    if upuser is None:
       raise HTTPException(status_code=401,detail='User is not authenticate')
    
    update_data = updateuser.model_dump(exclude_unset=True)

    for key,value in update_data.items():
        setattr(upuser,key,value)
    db.commit()

    return JSONResponse(status_code=200,content={'message':'User Updated Successfull'})

@router.put('/change-password')
def changePassword(db:db_dependency,user:user_dependency,upPass:PassworChange):
    if user is None:
        raise HTTPException(status_code=401,detail="Unauthenticate user")
    dbuser = db.query(Users).filter(Users.username == user.get('username')).first()

    if dbuser is None:
        raise HTTPException(status_code=404,detail="User not matching")
    

    if not bcrypt_context.verify(upPass.current_password,dbuser.password_hash):
        raise HTTPException(status_code=404,detail="Your current password does not matching")

    dbuser.password_hash = bcrypt_context.hash(upPass.new_password)
    db.commit()

    return JSONResponse(status_code=201,content={'message':'Your password has changed'})


@router.post("/forgot-password")
def ForgotPassword(db:db_dependency,newpassword:Createnewpassword):
    user = db.query(Users).filter(Users.username == newpassword.username).first()
    if user is None:
        raise HTTPException(status_code=401,detail="User Not Found")
    if user.email != newpassword.email:
        raise HTTPException(status_code=401,detail="Your Emailis wrong")
    user.password_hash = bcrypt_context.hash(newpassword.new_password)
    db.commit()
    return JSONResponse(status_code=200,content={'message':'New password set successfull'})