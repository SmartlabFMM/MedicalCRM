import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# =========================
# 1. Charger le dataset
# =========================
df = pd.read_csv("Health_Risk_Dataset.csv")

# =========================
# 2. Garder seulement les colonnes utiles
# =========================
df = df[["Temperature", "Heart_Rate", "Oxygen_Saturation", "Risk_Level"]].dropna()

print("Aperçu du dataset :")
print(df.head())
print("\nShape :", df.shape)

# =========================
# 3. Définir X et y
# =========================
X = df[["Temperature", "Heart_Rate", "Oxygen_Saturation"]]
y = df["Risk_Level"]

# =========================
# 4. Division train / test
# =========================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# =========================
# 5. Créer et entraîner le modèle
# =========================
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# =========================
# 6. Évaluation
# =========================
y_pred = model.predict(X_test)

print("\nAccuracy :", accuracy_score(y_test, y_pred))
print("\nClassification Report :\n")
print(classification_report(y_test, y_pred))

# =========================
# 7. Sauvegarder le modèle
# =========================
joblib.dump(model, "risk_model.pkl")
print("\nModèle sauvegardé sous : risk_model.pkl")

# =========================
# 8. Test avec un exemple
# =========================
sample = pd.DataFrame([{
    "Temperature": 38.2,
    "Heart_Rate": 110,
    "Oxygen_Saturation": 90
}])

prediction = model.predict(sample)[0]
print("\nPrédiction de test :", prediction)