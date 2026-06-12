# InspectShield Pro: Two-Stage Structural Surface Metrology Platform

InspectShield Pro is an enterprise-grade AI and computer vision platform engineered to automate concrete safety inspection tracking. The system pairs deep learning classification with deterministic mathematical computer vision algorithms to capture and compute physical fracture boundaries (width, length, and hazard severity metrics).

Upgraded from a simple script to a modern **multi-page full-stack SPA**, it features a secure **FastAPI backend**, **relational SQLite database**, **interactive calibration ruler**, and **background model optimization** dashboards.

---

## 🛠️ System Architecture

```text
                  +-----------------------------------+
                  |   InspectShield Pro Frontend SPA  |
                  |     (Vanilla JS & Custom CSS)     |
                  +-----------------------------------+
                                    |
                       JSON APIs & JWT Auth Tokens
                                    |
                                    v
                  +-----------------------------------+
                  |          FastAPI Server           |
                  |       (backend/main.py:8001)      |
                  +-----------------------------------+
                     /              |               \
        OpenCV Metrology    SQLAlchemy ORM     PyTorch Trainer
      (cv2_utils.py:Frangi)        |          (trainer.py:Thread)
             |                      v                      |
             |           +---------------------+           |
             |           |   SQLite Database   |           v
             v           | (inspectshield.db)  |      Checkpoints
       Visual Outputs    +---------------------+     (best_weights)
    (static/uploads/*.png)
```

### 1. Stage 1: Deep Learning Binary Filter Check
* **Backbone Options**: Supports dynamic swaps between `EfficientNet-B0` (edge execution), `EfficientNet-B2` (higher capacity), and `ResNet-34`.
* **Concatenated Pooling Classifier**: Replaced traditional single pooling with concatenated Global Average & Max Pooling to capture background texture details and localized sharp crevice peaks simultaneously.
* **Augmentation Suite**: Implements `ElasticTransform`, `GridDistortion`, and `CoarseDropout` to prevent overfitting to on-site lighting and camera shifts.

### 2. Stage 2: Computer Vision Metrology Engine
* **Frangi Vesselness Filter**: Uses a multi-scale Hessian-matrix filter to isolate tube-like fracture trajectories while ignoring circular concrete air bubbles, watermarks, or surface dust.
* **Width Computation**: Uses a Euclidean **Distance Transform** to find the widest part of the concrete crevice in millimeters.
* **Length Trajectory**: Implements a morphological **Skeletonization** routine that compresses the fissure down to a 1-pixel wide continuous centerline spine.

---

## ✨ Features

- **Auth Gatekeeper**: Secure logins with JWT access tokens and PBKDF2-HMAC-SHA256 password hashing.
- **Project Workspaces**: Group inspection audits under specific construction sites and export safety ledgers directly to CSV.
- **Interactive Ruler Calibration**: Draw a line on the upload canvas (e.g., overlaying an on-site ruler), input the physical distance in mm, and automatically calibrate pixels-to-mm.
- **Model Studio**: Trigger synthetic concrete data generation and monitor training curves and epoch losses in real-time.
- **Distribution Analytics**: Beautiful timeline graphs and safety distribution charts using Chart.js.

---

## 📂 Repository Index

* `backend/`
  * `main.py` — FastAPI router, authentication middleware, and API endpoints.
  * `database.py` — SQLAlchemy SQLite connection and session yielders.
  * `models.py` — Relational database models (Users, Projects, Inspections, ModelTrainings).
  * `auth.py` — Secure password hashing and token lifecycle controls.
  * `trainer.py` — PyTorch background worker thread.
  * `generate_synthetic.py` — Procedural gray concrete texture and Bezier crack generator.
* `frontend/`
  * `index.html` — SPA HTML panels (Dashboard, Projects, Metrology, Ledger, Model Studio).
  * `style.css` — Modern design system with default light theme and responsive cards.
  * `app.js` — SPA router, canvas calibration controller, and Chart.js compiler.
* `model.py` — PyTorch deep learning neural network graphs.
* `dataset.py` — Albumentations augmentations and training dataloaders.
* `cv2_utils.py` — Metrology logic containing the Frangi filter and morphological skeleton routines.
* `test_api.py` — Full integration test suite.

---

## 🚀 Quick Start Instructions

### 1. Install Dependencies
Make sure you have Python 3.10+ installed. Install the requirements:
```bash
pip install -r requirements.txt
```

### 2. Start the Server
Run the FastAPI application from the project root:
```bash
python backend/main.py
```
The application will automatically detect free ports and start (typically **`http://localhost:8001`**).

### 3. Generate Mock Data & Train Model
1. Open the website and register an account.
2. Go to the **Model Studio** panel.
3. Under **Seed Training Dataset**, click **Generate Synthetic Dataset** to write 30 cracked and 30 clean concrete textures to the server.
4. Under **Optimize Model Classifier**, select your backbone and epochs, and click **Run Model Optimization** to start training. Watch the logs update live!

### 4. Calibrate & Inspect
1. Go to the **Projects** panel and register a site.
2. Open the **Metrology Studio** and upload an image.
3. Click **Draw On-Image Ruler**, click-and-drag over your scale marker, input the physical length, and click **Calibrate Ratio**.
4. Click **Run Stage Metrology** to view the results side-by-side!
