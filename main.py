from fastapi import FastAPI, Depends, HTTPException
from database import Base, engine, SessionLocal
from models import *
from sqlalchemy.orm import Session
from schemas import UserCreate
from auth import hash_password, verify_password, create_token, verify_token
from datetime import datetime

app = FastAPI()

Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {"message": "Backend running 🚀"}


# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# REGISTER
@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    if user.role not in ["admin", "member"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    hashed = hash_password(user.password)

    new_user = User(
        name=user.name,
        email=user.email,
        password=hashed,
        role=user.role
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created successfully"}


# LOGIN
@app.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Wrong password")

    token = create_token({
        "user_id": user.id,
        "role": user.role
    })

    return {"access_token": token}

@app.get("/protected")
def protected(data=Depends(verify_token)):
    return {
        "message": "You are authorized",
        "user": data
    }

@app.post("/projects")
def create_project(name: str, user=Depends(verify_token), db: Session = Depends(get_db)):

    # check admin
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can create project")

    project = Project(
        name=name,
        created_by=user["user_id"]
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return {
        "message": "Project created successfully",
        "project_id": project.id
    }

@app.post("/projects/{project_id}/add-member")
def add_member(project_id: int, user_id: int,
               user=Depends(verify_token),
               db: Session = Depends(get_db)):

    # Only admin allowed
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can add members")

    # Check user exists
    member = db.query(User).filter(User.id == user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="User not found")

    # Add to project
    project_member = ProjectMember(
        project_id=project_id,
        user_id=user_id
    )

    db.add(project_member)
    db.commit()

    return {"message": "Member added to project"}

@app.post("/tasks")
def create_task(title: str, project_id: int, assigned_to: int,
                user=Depends(verify_token),
                db: Session = Depends(get_db)):

    # Only admin can create tasks
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can create tasks")

    # Check assigned user exists
    assigned_user = db.query(User).filter(User.id == assigned_to).first()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="Assigned user not found")

    task = Task(
        title=title,
        project_id=project_id,
        assigned_to=assigned_to
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return {
        "message": "Task created",
        "task_id": task.id
    }

@app.get("/tasks")
def get_tasks(user=Depends(verify_token), db: Session = Depends(get_db)):

    if user["role"] == "admin":
        tasks = db.query(Task).all()
    else:
        tasks = db.query(Task).filter(Task.assigned_to == user["user_id"]).all()

    return tasks

@app.put("/tasks/{task_id}")
def update_task(task_id: int, status: str,
                user=Depends(verify_token),
                db: Session = Depends(get_db)):

    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Only assigned user or admin can update
    if user["role"] != "admin" and task.assigned_to != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not allowed")

    task.status = status
    db.commit()

    return {"message": "Task updated"}

@app.get("/dashboard")
def dashboard(user=Depends(verify_token), db: Session = Depends(get_db)):

    if user["role"] == "admin":
        tasks = db.query(Task).all()
    else:
        tasks = db.query(Task).filter(Task.assigned_to == user["user_id"]).all()

    total = len(tasks)
    completed = len([t for t in tasks if t.status == "done"])
    pending = len([t for t in tasks if t.status != "done"])

    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "pending_tasks": pending
    }
