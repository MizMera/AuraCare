"""
Diabetes Monitor Views — AuraCare
===================================
Prédit la classe glycémique d'un résident diabétique et recommande
des aliments adaptés via un modèle LSTM entraîné sur Kaggle.

Dépendances :
    pip install tensorflow scikit-learn numpy

Fichiers requis dans backend/core/diabetes_model/ :
    - glucose_model.keras
    - glucose_scaler.pkl
    - glucose_meta.pkl
"""

import json
import logging
import os
import pickle
from pathlib import Path

import numpy as np
from rest_framework import views, status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Resident

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / 'diabetes_model'

# ── Chargement paresseux du modèle ─────────────────────────
_model  = None
_scaler = None
_meta   = None


def _load_artifacts():
    global _model, _scaler, _meta
    if _model is not None:
        return _model, _scaler, _meta, None

    model_path  = MODEL_DIR / 'glucose_model.keras'
    scaler_path = MODEL_DIR / 'glucose_scaler.pkl'
    meta_path   = MODEL_DIR / 'glucose_meta.pkl'

    missing = [str(p) for p in [model_path, scaler_path, meta_path] if not p.exists()]
    if missing:
        return None, None, None, (
            f"Fichiers manquants : {missing}. "
            "Entraînez le modèle sur Kaggle puis placez les fichiers dans backend/core/diabetes_model/"
        )

    try:
        import tensorflow as tf
        _model = tf.keras.models.load_model(str(model_path))
        with open(scaler_path, 'rb') as f:
            _scaler = pickle.load(f)
        with open(meta_path, 'rb') as f:
            _meta = pickle.load(f)
        logger.info("Modèle diabète chargé avec succès.")
        return _model, _scaler, _meta, None
    except Exception as e:
        return None, None, None, str(e)


def _classify_glucose_rule(blood_glucose_level: float) -> int:
    """Classification basée sur les seuils cliniques (fallback sans modèle)."""
    if blood_glucose_level < 70:   return 0
    elif blood_glucose_level < 140: return 1
    elif blood_glucose_level < 200: return 2
    else:                           return 3


# Métadonnées statiques (utilisées si le modèle n'est pas encore entraîné)
STATIC_META = {
    'features':    ['age', 'gender', 'bmi', 'HbA1c_level', 'blood_glucose_level',
                    'hypertension', 'heart_disease', 'smoking_history', 'diabetes'],
    'class_names': ['Hypoglycémie', 'Normale', 'Pré-Hyperglycémie', 'Hyperglycémie'],
    'class_thresholds': {
        0: {'label': 'Hypoglycémie',     'range': '<70 mg/dL',      'color': '#3B82F6'},
        1: {'label': 'Normale',          'range': '70-140 mg/dL',   'color': '#10B981'},
        2: {'label': 'Pré-Hyperglycémie','range': '140-200 mg/dL',  'color': '#F59E0B'},
        3: {'label': 'Hyperglycémie',    'range': '>200 mg/dL',     'color': '#EF4444'},
    },
    'meal_recommendations': {
        0: {
            'title': 'Glycémie basse — Apport rapide en sucre nécessaire',
            'urgent': True,
            'foods': [
                {'name': 'Jus de fruit (150ml)',        'gi': 'Élevé', 'carbs': '15g',  'icon': '🧃'},
                {'name': 'Glucose en comprimés (15g)',  'gi': 'Élevé', 'carbs': '15g',  'icon': '💊'},
                {'name': 'Miel (1 cuillère à soupe)',   'gi': 'Élevé', 'carbs': '17g',  'icon': '🍯'},
                {'name': 'Biscuits secs (3-4)',         'gi': 'Moyen', 'carbs': '20g',  'icon': '🍪'},
                {'name': 'Banane (1/2)',                'gi': 'Moyen', 'carbs': '12g',  'icon': '🍌'},
            ],
            'advice': 'Mesurez à nouveau dans 15 minutes. Si < 70 mg/dL, répétez.',
            'avoid':  ["Aliments gras (ralentissent l'absorption)"],
        },
        1: {
            'title': 'Glycémie normale — Repas équilibré recommandé',
            'urgent': False,
            'foods': [
                {'name': 'Riz complet (80g cuit)',      'gi': 'Moyen', 'carbs': '30g',  'icon': '🍚'},
                {'name': 'Poulet grillé (150g)',        'gi': 'Nul',   'carbs': '0g',   'icon': '🍗'},
                {'name': 'Légumes verts (200g)',        'gi': 'Faible','carbs': '10g',  'icon': '🥦'},
                {'name': 'Lentilles (100g cuites)',     'gi': 'Faible','carbs': '20g',  'icon': '🫘'},
                {'name': 'Yaourt nature (150g)',        'gi': 'Faible','carbs': '12g',  'icon': '🥛'},
                {'name': 'Pomme (1 moyenne)',           'gi': 'Faible','carbs': '25g',  'icon': '🍎'},
            ],
            'advice': 'Continuez vos repas équilibrés. Vérifiez dans 2h après repas.',
            'avoid':  ['Sucres raffinés en excès', 'Boissons sucrées'],
        },
        2: {
            'title': 'Glycémie élevée — Repas à faible index glycémique',
            'urgent': False,
            'foods': [
                {'name': 'Salade verte (200g)',         'gi': 'Faible','carbs': '5g',   'icon': '🥗'},
                {'name': 'Poisson vapeur (150g)',       'gi': 'Nul',   'carbs': '0g',   'icon': '🐟'},
                {'name': 'Courgette sautée (150g)',     'gi': 'Faible','carbs': '6g',   'icon': '🥒'},
                {'name': 'Haricots verts (100g)',       'gi': 'Faible','carbs': '7g',   'icon': '🫛'},
                {'name': 'Amandes (30g)',               'gi': 'Nul',   'carbs': '6g',   'icon': '🥜'},
                {'name': 'Pain complet (1 tranche)',    'gi': 'Moyen', 'carbs': '15g',  'icon': '🍞'},
            ],
            'advice': 'Évitez les sucres rapides. Marchez 15-20 min après le repas.',
            'avoid':  ['Pain blanc', 'Riz blanc', 'Pâtes blanches', 'Desserts sucrés'],
        },
        3: {
            'title': 'Hyperglycémie — Restriction glucidique stricte',
            'urgent': True,
            'foods': [
                {'name': 'Légumes crus (concombre, céleri)', 'gi': 'Faible','carbs': '3g', 'icon': '🥒'},
                {'name': 'Œufs brouillés (2)',          'gi': 'Nul',   'carbs': '0g',   'icon': '🥚'},
                {'name': 'Fromage blanc 0% (100g)',     'gi': 'Faible','carbs': '4g',   'icon': '🧀'},
                {'name': 'Tofu grillé (100g)',          'gi': 'Nul',   'carbs': '2g',   'icon': '🥩'},
                {'name': 'Bouillon de légumes',         'gi': 'Nul',   'carbs': '2g',   'icon': '🍵'},
            ],
            'advice': '⚠ Contactez l\'équipe médicale si > 250 mg/dL. Hydratez-vous bien.',
            'avoid':  ['Tout sucre', 'Fruits sucrés', 'Féculents', 'Jus de fruits'],
        },
    },
}


# ──────────────────────────────────────────────────────────────
# Vue 1 : Prédiction glycémie + recommandations repas
# ──────────────────────────────────────────────────────────────

class GlucosePredictView(views.APIView):
    """
    POST /api/diabetes/predict/
    Body JSON :
    {
      "resident_id":         3,
      "blood_glucose_level": 185.0,   ← mg/dL (requis)
      "HbA1c_level":         7.2,     ← % (optionnel, défaut 6.5)
      "bmi":                 28.5,    ← kg/m² (optionnel, défaut 27)
      "age":                 72,      ← ans (optionnel, défaut 70)
      "hypertension":        1,       ← 0/1 (optionnel)
      "heart_disease":       0,       ← 0/1 (optionnel)
    }

    Réponse :
    {
      "resident_id":    3,
      "resident_name":  "Jean Dupont",
      "blood_glucose":  185.0,
      "glucose_class":  2,
      "class_label":    "Pré-Hyperglycémie",
      "class_color":    "#F59E0B",
      "confidence":     87.4,          ← % (si modèle ML disponible)
      "model_used":     "LSTM" | "règles cliniques",
      "recommendation": {
        "title":  "...",
        "urgent": false,
        "foods":  [...],
        "advice": "...",
        "avoid":  [...]
      }
    }
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [JSONParser]

    def post(self, request, *args, **kwargs):
        # ── Validation des entrées ──────────────────────────
        resident_id        = request.data.get('resident_id')
        blood_glucose      = request.data.get('blood_glucose_level')

        if blood_glucose is None:
            return Response(
                {"error": "Champ 'blood_glucose_level' requis (mg/dL)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            blood_glucose = float(blood_glucose)
        except (TypeError, ValueError):
            return Response({"error": "blood_glucose_level doit être un nombre"}, status=400)

        if blood_glucose < 0 or blood_glucose > 600:
            return Response({"error": "blood_glucose_level hors plage (0-600 mg/dL)"}, status=400)

        # ── Récupération du résident ────────────────────────
        resident_name = "Résident"
        age           = float(request.data.get('age', 70))
        bmi           = float(request.data.get('bmi', 27.0))

        if resident_id:
            try:
                res           = Resident.objects.get(pk=resident_id)
                resident_name = res.name
                age           = float(res.age) if hasattr(res, 'age') else age
            except Resident.DoesNotExist:
                pass

        # ── Paramètres médicaux ────────────────────────────
        HbA1c        = float(request.data.get('HbA1c_level',   6.5))
        hypertension = int(request.data.get('hypertension',    0))
        heart_disease= int(request.data.get('heart_disease',   0))
        gender       = float(request.data.get('gender',        0.5))
        smoking      = float(request.data.get('smoking_history', 0))
        is_diabetic  = 1   # resident est diabétique par définition

        # ── Tentative de prédiction ML ─────────────────────
        model, scaler, meta, err = _load_artifacts()
        model_used  = "règles cliniques"
        confidence  = None
        glucose_class = None

        if model is not None and scaler is not None:
            try:
                features_order = meta['features']
                feature_map = {
                    'age':                age,
                    'gender':             gender,
                    'bmi':                bmi,
                    'HbA1c_level':        HbA1c,
                    'blood_glucose_level': blood_glucose,
                    'hypertension':       hypertension,
                    'heart_disease':      heart_disease,
                    'smoking_history':    smoking,
                    'diabetes':           is_diabetic,
                }
                X = np.array([[feature_map[f] for f in features_order]], dtype=np.float32)
                X_scaled = scaler.transform(X)
                X_lstm   = X_scaled.reshape((1, 1, X_scaled.shape[1]))

                probs       = model.predict(X_lstm, verbose=0)[0]
                glucose_class = int(np.argmax(probs))
                confidence    = round(float(np.max(probs)) * 100, 1)
                model_used    = "LSTM (AuraCare)"
            except Exception as e:
                logger.warning(f"Prédiction ML échouée, fallback clinique : {e}")

        # Fallback règles cliniques
        if glucose_class is None:
            glucose_class = _classify_glucose_rule(blood_glucose)

        # ── Métadonnées de la classe ────────────────────────
        active_meta = meta if meta else STATIC_META
        thresholds  = active_meta['class_thresholds']
        class_info  = thresholds.get(glucose_class, thresholds[1])
        reco        = active_meta['meal_recommendations'].get(glucose_class, {})

        return Response({
            "resident_id":    resident_id,
            "resident_name":  resident_name,
            "blood_glucose":  blood_glucose,
            "glucose_class":  glucose_class,
            "class_label":    class_info['label'],
            "class_color":    class_info['color'],
            "class_range":    class_info['range'],
            "confidence":     confidence,
            "model_used":     model_used,
            "recommendation": reco,
        })


# ──────────────────────────────────────────────────────────────
# Vue 2 : Historique des mesures d'un résident
# ──────────────────────────────────────────────────────────────

class GlucoseHistoryView(views.APIView):
    """
    GET  /api/diabetes/history/<resident_id>/
    POST /api/diabetes/history/<resident_id>/   → ajouter une mesure

    Stockage simple en base via le modèle GlucoseReading.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [JSONParser]

    def get(self, request, resident_id, *args, **kwargs):
        try:
            from .models import GlucoseReading
            readings = GlucoseReading.objects.filter(
                resident_id=resident_id
            ).order_by('-measured_at')[:30]

            data = [
                {
                    "id":           r.id,
                    "value":        r.blood_glucose,
                    "class":        r.glucose_class,
                    "class_label":  STATIC_META['class_names'][r.glucose_class],
                    "measured_at":  r.measured_at.isoformat(),
                    "notes":        r.notes,
                }
                for r in readings
            ]
            return Response({"readings": data, "count": len(data)})
        except Exception as e:
            return Response({"readings": [], "count": 0, "note": str(e)})

    def post(self, request, resident_id, *args, **kwargs):
        blood_glucose = request.data.get('blood_glucose_level')
        if blood_glucose is None:
            return Response({"error": "blood_glucose_level requis"}, status=400)

        glucose_class = _classify_glucose_rule(float(blood_glucose))

        try:
            from .models import GlucoseReading
            reading = GlucoseReading.objects.create(
                resident_id   = resident_id,
                blood_glucose = float(blood_glucose),
                glucose_class = glucose_class,
                notes         = request.data.get('notes', ''),
            )
            return Response({
                "success":      True,
                "id":           reading.id,
                "glucose_class": glucose_class,
                "class_label":   STATIC_META['class_names'][glucose_class],
                "measured_at":   reading.measured_at.isoformat(),
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# ──────────────────────────────────────────────────────────────
# Vue 3 : Statut du modèle
# ──────────────────────────────────────────────────────────────

class DiabetesModelStatusView(views.APIView):
    """GET /api/diabetes/status/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        _, _, meta, err = _load_artifacts()
        model_ready = err is None and meta is not None
        return Response({
            "model_ready":   model_ready,
            "model_dir":     str(MODEL_DIR),
            "error":         err,
            "kaggle_dataset": "https://www.kaggle.com/datasets/iammustafatz/diabetes-prediction-dataset",
            "training_script": "backend/core/train_diabetes_model.py",
            "files_needed":  [
                "glucose_model.keras",
                "glucose_scaler.pkl",
                "glucose_meta.pkl",
            ],
        })
