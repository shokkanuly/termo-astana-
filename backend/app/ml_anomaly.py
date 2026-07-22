import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

MODEL_DIR = os.path.dirname(os.path.abspath(__file__)) + "/models"
MODEL_PATH = MODEL_DIR + "/thermal_rf_model.joblib"

MATERIAL_R_MAPPING = {
    "modern_ventilated": 3.0,
    "glass_curtain": 1.2,
    "brick_soviet": 0.8,
    "brezhnevka_panel": 0.7,
    "khrushchyovka_panel": 0.4
}

def generate_mock_history_data(n_samples=5000):
    """Generates synthetic physics-informed history for normal state training."""
    np.random.seed(42)
    
    temp_in = np.random.uniform(20.0, 23.0, n_samples)
    temp_out = np.random.uniform(-35.0, 15.0, n_samples)
    humidity = np.random.uniform(30.0, 90.0, n_samples)
    wind_speed = np.random.uniform(0.0, 12.0, n_samples)
    
    facade_area = np.random.uniform(500.0, 8000.0, n_samples)
    
    materials = list(MATERIAL_R_MAPPING.keys())
    chosen_materials = np.random.choice(materials, n_samples)
    
    # Map materials to indices for sklearn
    material_idx = [materials.index(m) for m in chosen_materials]
    r_values = np.array([MATERIAL_R_MAPPING[m] for m in chosen_materials])
    
    # Fourier Law with wind convection factor (heat loss increases slightly with wind)
    delta_t = temp_in - temp_out
    base_loss_w = (facade_area * delta_t) / r_values
    wind_factor = 1.0 + (wind_speed * 0.04)
    noise = np.random.normal(0, base_loss_w * 0.05) # 5% Gaussian noise
    
    heat_loss_w = (base_loss_w * wind_factor) + noise
    # Clip negative values
    heat_loss_w = np.maximum(heat_loss_w, 0)
    
    df = pd.DataFrame({
        "temp_in": temp_in,
        "temp_out": temp_out,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "facade_area": facade_area,
        "material_idx": material_idx,
        "heat_loss": heat_loss_w / 1000.0 # Store in kW
    })
    
    return df

def train_offline_model():
    """Trains the RandomForest model and saves the binary."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    print("Generating training dataset...")
    df = generate_mock_history_data()
    
    X = df[["temp_in", "temp_out", "humidity", "wind_speed", "facade_area", "material_idx"]]
    y = df["heat_loss"]
    
    print("Training RandomForestRegressor model...")
    model = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
    model.fit(X, y)
    
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved successfully to {MODEL_PATH}")

_loaded_model = None

def get_anomaly_model():
    """Returns the pre-loaded model instance."""
    global _loaded_model
    if _loaded_model is None:
        if not os.path.exists(MODEL_PATH):
            print("Model binary not found. Training model now...")
            train_offline_model()
        _loaded_model = joblib.load(MODEL_PATH)
    return _loaded_model

def detect_anomaly(temp_in, temp_out, humidity, wind_speed, facade_area, material_preset, actual_loss_kw):
    """
    Predicts expected heat loss and checks if actual loss exceeds prediction by >35% threshold.
    """
    model = get_anomaly_model()
    materials = list(MATERIAL_R_MAPPING.keys())
    
    if material_preset not in materials:
        mat_idx = 0
    else:
        mat_idx = materials.index(material_preset)
        
    X_pred = np.array([[temp_in, temp_out, humidity, wind_speed, facade_area, mat_idx]])
    
    try:
        expected_loss_kw = float(model.predict(X_pred)[0])
    except Exception as e:
        print(f"ML inference error: {e}")
        # Physical model fallback
        r_val = MATERIAL_R_MAPPING.get(material_preset, 1.0)
        expected_loss_kw = (facade_area * (temp_in - temp_out)) / r_val / 1000.0
        
    deviation_pct = 0.0
    if expected_loss_kw > 0:
        deviation_pct = ((actual_loss_kw - expected_loss_kw) / expected_loss_kw) * 100.0
        
    # Anomaly condition: actual loss is 35% higher than expected baseline
    is_anomaly = deviation_pct > 35.0
    
    reason = ""
    if is_anomaly:
        if deviation_pct > 80.0:
            reason = f"КРИТИЧЕСКАЯ АНОМАЛИЯ: Потери на {deviation_pct:.1f}% выше нормы! Возможна разгерметизация швов или открыто окно."
        else:
            reason = f"Превышение потерь на {deviation_pct:.1f}%. Требуется инспекция теплоизоляции."
            
    return is_anomaly, reason, round(expected_loss_kw, 2)

# ─────────────────────────────────────────────
# TRAFFIC ANOMALY DETECTION (IsolationForest)
# ─────────────────────────────────────────────
from sklearn.ensemble import IsolationForest

TRAFFIC_FEATURES = ["traffic_speed_kmh", "congestion_index", "air_quality_co2_ppm", "facade_heat_loss_w_m2", "ambient_temp_c"]

print("Training IsolationForest traffic anomaly detector...")
np.random.seed(42)
_df_train = pd.DataFrame({
    "traffic_speed_kmh":      np.random.normal(50.0, 4.0, 300),
    "congestion_index":       np.random.normal(30.0, 4.0, 300),
    "air_quality_co2_ppm":    np.random.normal(410.0, 20.0, 300),
    "facade_heat_loss_w_m2":  np.random.normal(95.0,  8.0, 300),
    "ambient_temp_c":         np.random.normal(30.0,  0.5, 300),
})
traffic_ml_model = IsolationForest(contamination=0.05, random_state=42, n_estimators=150)
traffic_ml_model.fit(_df_train[TRAFFIC_FEATURES])
print("IsolationForest traffic model ready.")

def detect_traffic_anomaly(speed, congestion, co2, heat_loss, ambient_temp):
    df_test = pd.DataFrame([{
        "traffic_speed_kmh": speed,
        "congestion_index": congestion,
        "air_quality_co2_ppm": co2,
        "facade_heat_loss_w_m2": heat_loss,
        "ambient_temp_c": ambient_temp,
    }])
    prediction = traffic_ml_model.predict(df_test[TRAFFIC_FEATURES])[0]
    anomaly_score = float(traffic_ml_model.score_samples(df_test[TRAFFIC_FEATURES])[0])
    is_anomaly = bool(prediction == -1)
    confidence = round(max(0, min(100, (0.5 - anomaly_score) * 450))) if is_anomaly else 0
    return is_anomaly, anomaly_score, confidence

if __name__ == "__main__":
    train_offline_model()
