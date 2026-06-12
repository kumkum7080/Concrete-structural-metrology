import os
import sys
import cv2
import numpy as np
from fastapi.testclient import TestClient

# Add backend folder to path so main can be imported
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
from main import app

client = TestClient(app)

def run_integration_tests():
    print("=== STARTING INSPECTSHIELD PRO INTEGRATION TEST RUN ===")
    
    # 1. Prepare dummy concrete image
    img = np.ones((300, 300, 3), dtype=np.uint8) * 195
    # Draw a mock crack line (valleys/dark structures)
    cv2.line(img, (50, 150), (250, 150), (25, 25, 25), 3)
    
    img_path = "temp_test_concrete.png"
    cv2.imwrite(img_path, img)
    print(f"Created temporary mock concrete scan file: {img_path}")

    try:
        # 2. Register Inspector
        print("\n[STEP 1] Testing inspector account registration...")
        res = client.post(
            "/api/auth/register", 
            data={"username": "test_analyst", "password": "testpassword123"}
        )
        print(f"Register status: {res.status_code}")
        # Allow 400 if user already registered from a previous test run
        assert res.status_code in [201, 400], f"Failed registration: {res.text}"
        
        # 3. Log In Session
        print("\n[STEP 2] Testing inspector session establishment...")
        res = client.post(
            "/api/auth/login", 
            data={"username": "test_analyst", "password": "testpassword123"}
        )
        print(f"Login status: {res.status_code}")
        assert res.status_code == 200, f"Login failed: {res.text}"
        
        auth_data = res.json()
        token = auth_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Obtained JWT access token successfully.")

        # 4. Create Project Scope
        print("\n[STEP 3] Testing construction site project registration...")
        res = client.post(
            "/api/projects", 
            data={"name": "Highrise Tower B Column 4", "location": "Sector 9 Metro Site", "description": "Pre-pour inspection core samples"},
            headers=headers
        )
        print(f"Project creation status: {res.status_code}")
        assert res.status_code == 201, f"Project creation failed: {res.text}"
        project_id = res.json()["id"]
        print(f"Project created with ID: {project_id}")

        # 5. Run Two-Stage Metrology Upload
        print("\n[STEP 4] Testing metrology analysis upload...")
        with open(img_path, "rb") as f:
            files = {"file": (img_path, f, "image/png")}
            data = {
                "project_id": project_id,
                "pixel_to_mm_ratio": 0.15,
                "use_frangi": True,
                "frangi_thresh": 30,
                "force_stage_2": True,
                "notes": "Core sample integration test notes"
            }
            res = client.post("/api/inspections", data=data, files=files, headers=headers)
            
        print(f"Metrology upload status: {res.status_code}")
        assert res.status_code == 200, f"Metrology upload failed: {res.text}"
        
        metrics = res.json()
        print("Metrology calculations retrieved:")
        print(f"  Max Width: {metrics['max_width_mm']} mm")
        print(f"  Tracked Length: {metrics['length_mm']} mm")
        print(f"  Severity: {metrics['severity']}")
        
        assert metrics["max_width_mm"] > 0, "Width calculation should be greater than zero for cracked surfaces."
        assert metrics["length_mm"] > 0, "Length calculation should be greater than zero for cracked surfaces."
        inspection_id = metrics["id"]

        # 6. Retrieve Safety Ledger
        print("\n[STEP 5] Testing ledger query...")
        res = client.get(f"/api/inspections?project_id={project_id}", headers=headers)
        print(f"Query ledger status: {res.status_code}")
        assert res.status_code == 200, f"Ledger query failed: {res.text}"
        assert len(res.json()) >= 1, "Expected at least one inspection report."
        print(f"Ledger reports count: {len(res.json())}")

        # 7. Seed Synthetic Data trigger
        print("\n[STEP 6] Testing synthetic dataset generator trigger...")
        res = client.post("/api/models/synthetic", data={"count": 5}, headers=headers)
        print(f"Synthetic trigger status: {res.status_code}")
        assert res.status_code == 200, f"Synthetic generation failed: {res.text}"

        # 8. Clean up Inspection Audits
        print("\n[STEP 7] Purging inspection records...")
        res = client.delete(f"/api/inspections/{inspection_id}", headers=headers)
        print(f"Purge inspection status: {res.status_code}")
        assert res.status_code == 200, f"Purge inspection failed: {res.text}"

        # 9. Clean up Project Sites
        print("\n[STEP 8] Purging construction site record...")
        res = client.delete(f"/api/projects/{project_id}", headers=headers)
        print(f"Purge project status: {res.status_code}")
        assert res.status_code == 200, f"Purge project failed: {res.text}"

        print("\n=======================================================")
        print("SUCCESS: ALL SYSTEM INTEGRATION TESTS COMPLETED SUCCESSFULLY!")
        print("=======================================================")

    finally:
        # Erase temporary files
        if os.path.exists(img_path):
            os.remove(img_path)
            print(f"Erased temporary file: {img_path}")

if __name__ == "__main__":
    run_integration_tests()
