# app/routes/users.py

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.auth import get_password_hash, verify_password, create_access_token
from app.models import UserCreate

router = APIRouter()

# In-memory fake user database
fake_users_db = {}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate):
    print(user)
    if user.username in fake_users_db:
        raise HTTPException(status_code=400, detail="Username already registered")
    fake_users_db[user.username] = {
        "username": user.username,
        "hashed_password": get_password_hash(user.password),
    }
    return {"msg": "User registered successfully."}


@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = fake_users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}
