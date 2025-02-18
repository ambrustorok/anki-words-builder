# app/main.py

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routes import users
from app.auth.auth import get_current_user
from app.gradio.interface import demo
import gradio as gr

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Update with your frontend's origin
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

# Include user management endpoints (register, token, etc.)
app.include_router(users.router, prefix="")


# Optional: Protected endpoint to get current user info.
@app.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/protected")
async def protected_route(current_user: dict = Depends(get_current_user)):
    return {"message": f"Hello, {current_user['username']}! You are authenticated."}


# Mount the Gradio app on the path "/gradio"
# The auth_dependency ensures that only authenticated users (per get_current_user) can access it.
app = gr.mount_gradio_app(
    app,
    demo,
    path="/gradio",
    auth_dependency=get_current_user,
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
