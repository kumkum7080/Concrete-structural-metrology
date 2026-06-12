import os
import sys
import uuid
import shutil
import threading
from typing import List, Optional
from datetime import datetime

import cv2
import numpy as np
import torch
import albumentations as A
from albumentations.pytorch import ToTensorV2

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session

# Import backend modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import engine, get_db, Base
from models import User, Project, Inspection, ModelTraining
from auth import verify_password, get_password_hash, create_access_token, decode_access_token
from cv2_utils import analyze_crack_dimensions
from model import ConcreteInspectionNet
from trainer import run_training_session

# Initialize DB tables
Base.metadata.create_all(bind=engine)

# Setup directories
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Global variables for model state
ACTIVE_MODEL = None
CURRENT_BACKBONE = "efficientnet_b0"
model_lock = threading.Lock()

def load_active_model(backbone_name="efficientnet_b0"):
    global ACTIVE_MODEL, CURRENT_BACKBONE
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    with model_lock:
        try:
            # Initialize with pretrained=False to avoid unnecessary web requests during runtime unless training
            model = ConcreteInspectionNet(backbone_name=backbone_name, num_classes=2, pretrained=False)
            weights_path = os.path.join(os.path.dirname(__file__), "..", "best_concrete_model.pth")
            
            if os.path.exists(weights_path):
                model.load_state_dict(torch.load(weights_path, map_location=device))
                print(f"Loaded active model weights from {weights_path}")
            else:
                print("No active model checkpoint (best_concrete_model.pth) found. Model running with default parameters.")
                
            model.to(device).eval()
            ACTIVE_MODEL = model
            CURRENT_BACKBONE = backbone_name
        except Exception as e:
            print(f"Error loading active model: {e}")
            ACTIVE_MODEL = None

# Load model on start
load_active_model("efficientnet_b0")

# FastAPI App
app = FastAPI(title="InspectShield Pro Metrology API", version="1.0.0")

# CORS middleware for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication Dependency
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


# --- AUTHENTICATION ROUTES ---

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already cataloged in database.")
    
    # Hash password and save
    hashed = get_password_hash(password)
    # Check if this is the first user; if so, make them an admin
    user_count = db.query(User).count()
    role = "administrator" if user_count == 0 else "inspector"
    
    new_user = User(username=username, password_hash=hashed, role=role)
    db.add(new_user)
    db.commit()
    return {"message": "Account registered successfully", "username": username, "role": role}

@app.post("/api/auth/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid structural credentials.")
    
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "username": user.username, "role": user.role}

@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role, "id": current_user.id}


# --- PROJECT MANAGEMENT ROUTES ---

@app.get("/api/projects", response_model=list)
def get_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    projects = db.query(Project).filter(Project.user_id == current_user.id).order_by(Project.created_at.desc()).all()
    return [{"id": p.id, "name": p.name, "location": p.location, "description": p.description, "created_at": p.created_at.isoformat()} for p in projects]

@app.post("/api/projects", status_code=status.HTTP_201_CREATED)
def create_project(
    name: str = Form(...),
    location: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = Project(name=name, location=location, description=description, user_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name, "location": project.location, "description": project.description}

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized access.")
    db.delete(project)
    db.commit()
    return {"message": "Project and associated audits deleted successfully"}


# --- METROLOGY & INSPECTION ROUTES ---

@app.get("/api/inspections")
def get_inspections(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Inspection).filter(Inspection.user_id == current_user.id)
    if project_id:
        query = query.filter(Inspection.project_id == project_id)
    inspections = query.order_by(Inspection.created_at.desc()).all()
    
    result = []
    for ins in inspections:
        project_name = ins.project.name if ins.project else "Unassigned"
        result.append({
            "id": ins.id,
            "project_id": ins.project_id,
            "project_name": project_name,
            "filename": ins.filename,
            "raw_image_path": f"/static/uploads/{os.path.basename(ins.raw_image_path)}",
            "mask_path": f"/static/uploads/{os.path.basename(ins.mask_path)}",
            "skeleton_path": f"/static/uploads/{os.path.basename(ins.skeleton_path)}",
            "max_width_mm": ins.max_width_mm,
            "length_mm": ins.length_mm,
            "severity": ins.severity,
            "notes": ins.notes,
            "created_at": ins.created_at.isoformat()
        })
    return result

@app.post("/api/inspections")
async def analyze_inspection(
    file: UploadFile = File(...),
    project_id: Optional[int] = Form(None),
    pixel_to_mm_ratio: float = Form(0.15),
    use_frangi: bool = Form(True),
    frangi_thresh: int = Form(40),
    force_stage_2: bool = Form(False),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Create unique folder and filenames
    uid = uuid.uuid4().hex
    raw_name = f"raw_{uid}_{file.filename}"
    mask_name = f"mask_{uid}.png"
    skel_name = f"skel_{uid}.png"
    
    raw_path = os.path.join(UPLOADS_DIR, raw_name)
    mask_path = os.path.join(UPLOADS_DIR, mask_name)
    skel_path = os.path.join(UPLOADS_DIR, skel_name)
    
    # Save raw file
    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Validate Project ID ownership
    if project_id:
        proj = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
        if not proj:
            project_id = None

    # Step 1: Deep Learning Binary check
    classification = 1  # Default to anomaly flagged if no model is loaded
    confidence = 100.0
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    global ACTIVE_MODEL
    if ACTIVE_MODEL is not None and not force_stage_2:
        try:
            raw_img = cv2.imread(raw_path)
            rgb_img = cv2.cvtColor(raw_img, cv2.COLOR_BGR2RGB)
            
            transform = A.Compose([
                A.Resize(224, 224),
                A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
                ToTensorV2()
            ])
            tensor_img = transform(image=rgb_img)['image'].unsqueeze(0).to(device)
            
            with torch.no_grad():
                logits = ACTIVE_MODEL(tensor_img)
                probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
                classification = int(np.argmax(probs))
                confidence = float(probs[classification] * 100)
        except Exception as e:
            print(f"Error during deep learning Stage 1: {e}")
            classification = 1  # Fail-safe: run CV

    # Step 2: Metrology Engine
    if classification == 0 and not force_stage_2:
        # Surface Intact - No crack calculations needed
        severity = "Surface Intact (No Defect)"
        width = 0.0
        length = 0.0
        
        # Save dummy visual elements (copy original as mask/skel for visual UI consistency)
        shutil.copyfile(raw_path, mask_path)
        shutil.copyfile(raw_path, skel_path)
    else:
        # Crack detected or Stage 2 execution forced
        metrology_results = analyze_crack_dimensions(
            raw_path, pixel_to_mm_ratio=pixel_to_mm_ratio, use_frangi=use_frangi, frangi_thresh=frangi_thresh
        )
        
        if metrology_results is None:
            raise HTTPException(status_code=500, detail="Metrology extraction engine failed.")
            
        width, length, severity, mask_img, skel_img = metrology_results
        
        # Save output images
        cv2.imwrite(mask_path, mask_img)
        cv2.imwrite(skel_path, skel_img)

    # Save to database
    inspection = Inspection(
        project_id=project_id,
        user_id=current_user.id,
        filename=file.filename,
        raw_image_path=raw_path,
        mask_path=mask_path,
        skeleton_path=skel_path,
        max_width_mm=width,
        length_mm=length,
        severity=severity,
        notes=notes
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    
    return {
        "id": inspection.id,
        "filename": inspection.filename,
        "max_width_mm": width,
        "length_mm": length,
        "severity": severity,
        "stage1_classification": "Anomaly Flagged" if (classification == 1 or force_stage_2) else "Surface Intact",
        "stage1_confidence": round(confidence, 2),
        "raw_image_url": f"/static/uploads/{raw_name}",
        "mask_url": f"/static/uploads/{mask_name}",
        "skeleton_url": f"/static/uploads/{skel_name}"
    }

@app.delete("/api/inspections/{inspection_id}")
def delete_inspection(inspection_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ins = db.query(Inspection).filter(Inspection.id == inspection_id, Inspection.user_id == current_user.id).first()
    if not ins:
        raise HTTPException(status_code=404, detail="Inspection report not cataloged or access denied.")
    
    # Remove local image assets
    for path in [ins.raw_image_path, ins.mask_path, ins.skeleton_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
                
    db.delete(ins)
    db.commit()
    return {"message": "Inspection audit file purged successfully."}


# --- DATA EXPORT ROUTES ---

@app.get("/api/reports/export")
def export_history_csv(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inspections = db.query(Inspection).filter(Inspection.user_id == current_user.id).order_by(Inspection.created_at.desc()).all()
    
    def generate():
        # Header row
        yield "ID,Timestamp,Project,Filename,Max Width (mm),Length (mm),Severity,Notes\n"
        for ins in inspections:
            p_name = ins.project.name if ins.project else "Unassigned"
            notes_clean = ins.notes.replace('"', '""') if ins.notes else ""
            yield f'{ins.id},{ins.created_at.strftime("%Y-%m-%d %H:%M:%S")},"{p_name}","{ins.filename}",{ins.max_width_mm},{ins.length_mm},"{ins.severity}","{notes_clean}"\n'

    headers = {
        "Content-Disposition": f"attachment; filename=inspectshield_{current_user.username}_history.csv",
        "Content-Type": "text/csv"
    }
    return StreamingResponse(generate(), headers=headers)


# --- MODEL TRAINING AND MANAGEMENT ---

@app.get("/api/models/active")
def get_active_model_details():
    global CURRENT_BACKBONE, ACTIVE_MODEL
    weights_path = os.path.join(os.path.dirname(__file__), "..", "best_concrete_model.pth")
    has_weights = os.path.exists(weights_path)
    
    return {
        "active_backbone": CURRENT_BACKBONE,
        "weights_loaded": has_weights,
        "device": "GPU/CUDA" if torch.cuda.is_available() else "CPU",
        "last_modified": datetime.fromtimestamp(os.path.getmtime(weights_path)).isoformat() if has_weights else None
    }

@app.post("/api/models/active")
def change_active_backbone(backbone_name: str = Form(...), current_user: User = Depends(get_current_user)):
    if current_user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator role credentials required.")
    
    if backbone_name not in ["efficientnet_b0", "efficientnet_b2", "resnet34"]:
        raise HTTPException(status_code=400, detail="Invalid backbone choice selection.")
        
    load_active_model(backbone_name)
    return {"message": f"Successfully activated backbone {backbone_name}."}

@app.post("/api/models/train", status_code=status.HTTP_201_CREATED)
def trigger_training(
    backbone_name: str = Form("efficientnet_b0"),
    epochs: int = Form(5),
    bg_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if a training job is already active/running
    running_job = db.query(ModelTraining).filter(ModelTraining.status == "running").first()
    if running_job:
        raise HTTPException(status_code=400, detail="Another model optimization session is currently active.")
        
    # Verify dataset directories
    pos_dir = os.path.join(DATA_DIR, "Positive")
    neg_dir = os.path.join(DATA_DIR, "Negative")
    
    # If folder is empty, throw error
    if not os.path.exists(pos_dir) or not os.path.exists(neg_dir) or \
       len(os.listdir(pos_dir)) == 0 or len(os.listdir(neg_dir)) == 0:
        raise HTTPException(
            status_code=400, 
            detail="Insufficient dataset resources. Please seed synthetic concrete textures or upload files to '/data/Positive' and '/data/Negative'."
        )

    # Create training session record in DB
    job = ModelTraining(status="queued", epochs=epochs, current_epoch=0, logs="Queuing optimization tasks...")
    db.add(job)
    db.commit()
    db.refresh(job)

    # Launch PyTorch background training loop
    bg_tasks.add_task(run_training_session, job.id, DATA_DIR, epochs, backbone_name)
    
    return {"message": "Model optimization queued.", "training_id": job.id}

@app.get("/api/models/training-status")
def get_training_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sessions = db.query(ModelTraining).order_by(ModelTraining.created_at.desc()).all()
    return [{
        "id": s.id,
        "status": s.status,
        "epochs": s.epochs,
        "current_epoch": s.current_epoch,
        "loss": s.loss,
        "accuracy": s.accuracy,
        "logs": s.logs,
        "created_at": s.created_at.isoformat()
    } for s in sessions]

@app.post("/api/models/synthetic")
def trigger_synthetic_generation(count: int = Form(30), current_user: User = Depends(get_current_user)):
    """Triggers generation of synthetic dataset samples for quick system testing."""
    if current_user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator role credentials required.")
        
    try:
        from generate_synthetic import create_dataset
        # Run in thread so as not to freeze API response
        t = threading.Thread(target=create_dataset, args=(DATA_DIR, count))
        t.start()
        return {"message": f"Dataset generation of {count} files per class started in background."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


# --- FRONTEND ROUTING & STATIC STATIC MOUNTING ---

# Mount uploads static folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Mount frontend files at the root
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    import socket
    
    def find_free_port(start_port=8000, max_port=8100):
        for p in range(start_port, max_port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", p))
                    return p
                except OSError:
                    continue
        return 8080  # Fallback

    free_port = find_free_port(8000, 8100)
    print(f"Dynamically selected free port: {free_port}")
    uvicorn.run("main:app", host="127.0.0.1", port=free_port, reload=True)
