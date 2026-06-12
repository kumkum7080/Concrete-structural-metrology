import streamlit as st
import torch
import numpy as np
import cv2
import os
import albumentations as A
from albumentations.pytorch import ToTensorV2
from model import ConcreteInspectionNet
from cv2_utils import analyze_crack_dimensions
from database import log_inspection

st.set_page_config(page_title="Metrology Dashboard", page_icon="📊", layout="wide")

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("🔒 Access Blocked. Please log in on the main gateway page first.")
    st.stop()

st.title("🎛️ Inspection Command Center")

st.sidebar.markdown("### Metrology Calibration")
ratio = st.sidebar.slider("Pixel-to-mm Scaling Ratio", min_value=0.05, max_value=0.50, value=0.15, step=0.01)

uploaded_file = st.file_uploader("Choose a surface scan image...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    temp_path = os.path.join(".", uploaded_file.name)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    with st.spinner("Executing Stage 1 Deep Learning Inference..."):
        model = ConcreteInspectionNet(pretrained=False)
        # Fallback to initialized initialization if weights are not local
        WEIGHTS_PATH = "best_concrete_model.pth"
        
        if os.path.exists(WEIGHTS_PATH):
            model.load_state_dict(torch.load(WEIGHTS_PATH, map_location=device))
        model.to(device).eval()

        raw_img = cv2.imread(temp_path)
        rgb_img = cv2.cvtColor(raw_img, cv2.COLOR_BGR2RGB)

        transform = A.Compose([
            A.Resize(224, 224),
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2()
        ])
        tensor_img = transform(image=rgb_img)['image'].unsqueeze(0).to(device)

        with torch.no_grad():
            logits = model(tensor_img)
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
            classification = np.argmax(probs)

    if classification == 0:
        st.markdown(f"""
            <div style="background-color:#E2F0D9; padding:20px; border-radius:8px; border-left:8px solid #70AD47; margin-bottom:20px;">
                <h3 style="color:#385723; margin:0;">✅ STAGE 1 RESULT: SURFACE INTACT</h3>
                <p style="color:#385723; margin:5px 0 0 0;">Confidence Rating: {probs[0]*100:.2f}% | No structural anomalies detected.</p>
            </div>
        """, unsafe_allow_html=True)
        st.image(rgb_img, caption="Inspected Smooth Concrete Surface", width=400)
    else:
        width, length, category, mask, skeleton = analyze_crack_dimensions(temp_path, pixel_to_mm_ratio=ratio)

        if width < 0.3:
            bg_color, border_color, text_color, badge_label = "#E2F0D9", "#70AD47", "#385723", "SAFE (HAIRLINE)"
        elif width <= 1.2:
            bg_color, border_color, text_color, badge_label = "#FFF2CC", "#FFC000", "#7F6000", "WARNING (MODERATE RISK)"
        else:
            bg_color, border_color, text_color, badge_label = "#FCE4D6", "#C65911", "#833C0C", "CRITICAL BREAK (HIGH RISK)"

        st.markdown(f"""
            <div style="background-color:{bg_color}; padding:20px; border-radius:8px; border-left:8px solid {border_color}; margin-bottom:25px;">
                <h3 style="color:{text_color}; margin:0;">🚨 STAGE 1 ANOMALY FLAG & STAGE 2 METROLOGY</h3>
                <p style="color:{text_color}; font-weight:bold; margin:5px 0 0 0;">Status: {badge_label}</p>
            </div>
        """, unsafe_allow_html=True)

        log_inspection(st.session_state.username, uploaded_file.name, width, length, badge_label)

        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Maximum Crack Width", f"{width} mm")
        m_col2.metric("Total Line Path Length", f"{length} mm")
        m_col3.metric("Evaluated Hazard Severity", category)

        st.write("---")
        t1, t2 = st.tabs([" Visual Matrix", " Diagnostic Metrics"])

        with t1:
            v_col1, v_col2 = st.columns(2)
            v_col1.image(rgb_img, caption="Input Field Scan", use_container_width=True)
            v_col2.image(mask, caption="Stage 2 Segmentation Mask", use_container_width=True)

        with t2:
            s_col1, s_col2 = st.columns(2)
            s_col1.image(skeleton, caption="Calculated Mathematical Spine Line", use_container_width=True)
            s_col2.markdown(f"""
                ### 📋 Asset Maintenance Strategy
                * **Calculated Width Index:** {width} mm
                * **Calculated Length Index:** {length} mm
                * **Structural Action Item:** Metric points automatically archived. Review structural audit ledger trends to monitor propagation velocities.
            """)
            
    if os.path.exists(temp_path):
        os.remove(temp_path)
