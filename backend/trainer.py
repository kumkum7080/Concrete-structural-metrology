import os
import sys
import torch
import torch.nn as nn
import torch.optim as optim
import traceback
from datetime import datetime

# Adjust path to import model and dataset from root folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal
from models import ModelTraining
from model import ConcreteInspectionNet
from dataset import build_loaders

def run_training_session(training_id: int, data_dir: str, epochs: int, backbone_name: str):
    """
    Trains the ConcreteInspectionNet in a background thread.
    Updates the database record at each epoch with progress and metrics.
    """
    db = SessionLocal()
    training_record = db.query(ModelTraining).filter(ModelTraining.id == training_id).first()
    
    if not training_record:
        print(f"Training session ID {training_id} not found in database.")
        db.close()
        return

    try:
        # Update state to running
        training_record.status = "running"
        training_record.logs = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] starting training session...\n"
        training_record.logs += f"Backbone: {backbone_name} | Target Epochs: {epochs}\n"
        training_record.logs += f"Data directory: {data_dir}\n"
        db.commit()

        # Step 1: Build Loaders
        training_record.logs += f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scanning data directory and building loaders...\n"
        db.commit()
        
        # Batch size fallback depending on CPU/GPU
        batch_size = 16 if not torch.cuda.is_available() else 32
        
        try:
            train_loader, val_loader = build_loaders(data_dir, batch_size=batch_size)
        except Exception as loader_err:
            raise RuntimeError(f"Failed to load datasets. Verify that 'Positive' and 'Negative' directories exist with image files. Details: {str(loader_err)}")

        num_train = len(train_loader.dataset)
        num_val = len(val_loader.dataset)
        training_record.logs += f"Loaded {num_train} training samples and {num_val} validation samples.\n"
        db.commit()

        # Step 2: Initialize Model
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        training_record.logs += f"Using execution device: {device.type.upper()}\n"
        db.commit()

        model = ConcreteInspectionNet(backbone_name=backbone_name, num_classes=2, pretrained=True)
        model.to(device)

        # Step 3: Define Loss and Optimizer
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-3)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        best_val_acc = 0.0
        weights_dir = os.path.join(os.path.dirname(__file__), "..", "checkpoints")
        os.makedirs(weights_dir, exist_ok=True)
        checkpoint_filename = f"weights_training_{training_id}.pth"
        checkpoint_path = os.path.join(weights_dir, checkpoint_filename)

        training_record.logs += f"Initializing training loops...\n"
        db.commit()

        for epoch in range(1, epochs + 1):
            training_record.current_epoch = epoch
            
            # --- Training Loop ---
            model.train()
            train_loss = 0.0
            train_correct = 0
            total_train_samples = 0

            for images, labels in train_loader:
                images, labels = images.to(device), labels.to(device)
                
                optimizer.zero_grad()
                outputs = model(images)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                train_loss += loss.item() * images.size(0)
                _, preds = torch.max(outputs, 1)
                train_correct += torch.sum(preds == labels.data).item()
                total_train_samples += images.size(0)

            scheduler.step()
            epoch_train_loss = train_loss / total_train_samples
            epoch_train_acc = train_correct / total_train_samples

            # --- Validation Loop ---
            model.eval()
            val_loss = 0.0
            val_correct = 0
            total_val_samples = 0

            with torch.no_grad():
                for images, labels in val_loader:
                    images, labels = images.to(device), labels.to(device)
                    outputs = model(images)
                    loss = criterion(outputs, labels)

                    val_loss += loss.item() * images.size(0)
                    _, preds = torch.max(outputs, 1)
                    val_correct += torch.sum(preds == labels.data).item()
                    total_val_samples += images.size(0)

            epoch_val_loss = val_loss / total_val_samples
            epoch_val_acc = val_correct / total_val_samples

            # Save best checkpoint
            if epoch_val_acc > best_val_acc:
                best_val_acc = epoch_val_acc
                torch.save(model.state_dict(), checkpoint_path)
                training_record.model_path = os.path.abspath(checkpoint_path)
                db.commit()

            # Record stats
            training_record.loss = round(epoch_val_loss, 4)
            training_record.accuracy = round(epoch_val_acc, 4)
            
            epoch_log = (f"[{datetime.now().strftime('%H:%M:%S')}] Epoch {epoch}/{epochs} | "
                         f"Train Loss: {epoch_train_loss:.4f} Acc: {epoch_train_acc*100:.2f}% | "
                         f"Val Loss: {epoch_val_loss:.4f} Acc: {epoch_val_acc*100:.2f}%"
                         + (" *Best Model Saved*" if epoch_val_acc == best_val_acc else "")
                         + "\n")
            
            training_record.logs += epoch_log
            db.commit()

        # Step 4: Complete Training Session
        training_record.status = "completed"
        training_record.logs += f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Training complete! Best validation accuracy: {best_val_acc*100:.2f}%\n"
        
        # Copy checkpoint to best_concrete_model.pth in root directory to act as primary runtime weights
        primary_weights_path = os.path.join(os.path.dirname(__file__), "..", "best_concrete_model.pth")
        if os.path.exists(checkpoint_path):
            import shutil
            shutil.copy(checkpoint_path, primary_weights_path)
            training_record.logs += f"Activated trained weights as primary model weights (best_concrete_model.pth).\n"
            
        db.commit()

    except Exception as err:
        # Save traceback logs on fail
        err_msg = traceback.format_exc()
        print(f"Error during training session {training_id}: {str(err)}")
        training_record.status = "failed"
        training_record.logs += f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR OCCURRED:\n{err_msg}\n"
        db.commit()

    finally:
        db.close()
