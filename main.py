from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import Base, engine, get_db
from models import User, Project, Task, ProjectMember
from schemas import UserCreate
from auth import hash_password, verify_password, create_token, verify_token
from pydantic import BaseModel
from typing import List

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)


# ===================== SCHEMAS =====================

class LoginSchema(BaseModel):
    email: str
    password: str


class ProjectCreate(BaseModel):
    name: str


class AddMemberSchema(BaseModel):
    user_id: int


class TaskCreate(BaseModel):
    title: str
    project_id: int
    assigned_to: int


class TaskUpdate(BaseModel):
    status: str


# ===================== ROUTES =====================

@app.get("/")
def home():
    return {"message": "Backend running 🚀"}


# ===================== AUTH =====================

@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    if user.role not in ["admin", "member"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    hashed_password = hash_password(user.password)

    new_user = User(
        name=user.name,
        email=user.email,
        password=hashed_password,
        role=user.role
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created successfully"}


@app.post("/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == data.email).first()

    # 🔐 Secure auth (no info leak)
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = create_token({
        "user_id": user.id,
        "role": user.role
    })

    return {"access_token": token}


@app.get("/protected")
def protected(user=Depends(verify_token)):
    return {
        "message": "Authorized",
        "user": user
    }


# ===================== PROJECTS =====================

@app.post("/projects")
def create_project(
    data: ProjectCreate,
    user=Depends(verify_token),
    db: Session = Depends(get_db)
):

    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can create project")

    project = Project(
        name=data.name,
        created_by=user["user_id"]
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return {
        "message": "Project created",
        "project_id": project.id
    }


@app.post("/projects/{project_id}/add-member")
def add_member(
    project_id: int,
    data: AddMemberSchema,
    user=Depends(verify_token),
    db: Session = Depends(get_db)
):

    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can add members")

    # Check project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check user exists
    member = db.query(User).filter(User.id == data.user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent duplicate
    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == data.user_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="User already in project")

    project_member = ProjectMember(
        project_id=project_id,
        user_id=data.user_id
    )

    db.add(project_member)
    db.commit()

    return {"message": "Member added to project"}


# ===================== TASKS =====================

@app.post("/tasks")
def create_task(
    data: TaskCreate,
    user=Depends(verify_token),
    db: Session = Depends(get_db)
):

    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can create tasks")

    # Check project
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check assigned user
    assigned_user = db.query(User).filter(User.id == data.assigned_to).first()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="Assigned user not found")

    task = Task(
        title=data.title,
        project_id=data.project_id,
        assigned_to=data.assigned_to
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

    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "project_id": t.project_id
        }
        for t in tasks
    ]


@app.put("/tasks/{task_id}")
def update_task(
    task_id: int,
    data: TaskUpdate,
    user=Depends(verify_token),
    db: Session = Depends(get_db)
):

    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if user["role"] != "admin" and task.assigned_to != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not allowed")

    # Validate status
    if data.status not in ["todo", "in-progress", "done"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    task.status = data.status
    db.commit()

    return {"message": "Task updated"}


# ===================== DASHBOARD =====================

@app.get("/dashboard")
def dashboard(user=Depends(verify_token), db: Session = Depends(get_db)):

    if user["role"] == "admin":
        tasks = db.query(Task).all()
    else:
        tasks = db.query(Task).filter(Task.assigned_to == user["user_id"]).all()

    total = len(tasks)
    completed = len([t for t in tasks if t.status == "done"])
    pending = total - completed

    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "pending_tasks": pending
    }