"""
Face Recognition Views — AuraCare
==================================
Fonctionnalités :
  1. Upload / remplacement de la photo d'un résident → calcul et stockage de l'encodage facial
  2. Identification en temps réel : reçoit une frame JPEG encodée en base64,
     retourne les résidents reconnus avec leur score de confiance.

Dépendances Python :
    pip install insightface onnxruntime pillow numpy opencv-python-headless

insightface utilise ONNX Runtime (pas besoin de dlib ni de GPU).
Le modèle buffalo_l sera téléchargé automatiquement au premier lancement (~300 MB).
"""

import base64
import io
import json
import logging

import cv2
import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import views, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Resident, FaceEncoding

logger = logging.getLogger(__name__)

# ── Seuil de similarité cosinus (0.0 = différent, 1.0 = identique) ──
# Équivalent à une tolérance de 0.52 dans face_recognition
FACE_SIMILARITY_THRESHOLD = 0.40


# ──────────────────────────────────────────────────────────────
# Initialisation d'InsightFace (singleton)
# ──────────────────────────────────────────────────────────────

_insightface_app = None

def _get_insightface_app():
    """
    Retourne l'instance InsightFace (initialisée une seule fois).
    ctx_id=-1 → CPU uniquement (pas besoin de GPU).
    """
    global _insightface_app
    if _insightface_app is None:
        try:
            from insightface.app import FaceAnalysis
            _insightface_app = FaceAnalysis(
                name='buffalo_l',
                providers=['CPUExecutionProvider']
            )
            _insightface_app.prepare(ctx_id=-1, det_size=(640, 640))
            logger.info("InsightFace initialisé avec succès.")
        except Exception as e:
            logger.error(f"Impossible d'initialiser InsightFace : {e}")
            return None
    return _insightface_app


# ──────────────────────────────────────────────────────────────
# Fonctions utilitaires
# ──────────────────────────────────────────────────────────────

def _pil_to_bgr(pil_image):
    """Convertit une image PIL RGB en tableau numpy BGR (pour OpenCV/InsightFace)."""
    img_rgb = np.array(pil_image.convert("RGB"))
    return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)


def _compute_encoding(image_bytes: bytes):
    """
    Calcule l'encodage facial 512-dim depuis les bytes d'une image.
    Retourne (encoding_array, error_str).
    """
    face_app = _get_insightface_app()
    if face_app is None:
        return None, "insightface non disponible sur le serveur"

    try:
        from PIL import Image
        img_pil = Image.open(io.BytesIO(image_bytes))
        img_bgr = _pil_to_bgr(img_pil)
    except Exception as e:
        return None, f"Impossible de lire l'image : {e}"

    faces = face_app.get(img_bgr)

    if not faces:
        return None, "Aucun visage détecté dans l'image"
    if len(faces) > 1:
        return None, f"{len(faces)} visages détectés — utilisez une photo avec un seul visage"

    return faces[0].embedding, None


def _cosine_similarity(enc1: np.ndarray, enc2: np.ndarray) -> float:
    """Similarité cosinus entre deux vecteurs (résultat entre -1 et 1)."""
    norm1 = np.linalg.norm(enc1)
    norm2 = np.linalg.norm(enc2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(enc1, enc2) / (norm1 * norm2))


def _cosine_similarities(known_encodings: list, unknown_encoding: np.ndarray) -> np.ndarray:
    """Calcule la similarité cosinus entre un encodage inconnu et tous les encodages connus."""
    if not known_encodings:
        return np.array([])
    known_matrix = np.stack(known_encodings)          # (N, 512)
    norms = np.linalg.norm(known_matrix, axis=1)      # (N,)
    unknown_norm = np.linalg.norm(unknown_encoding)
    if unknown_norm == 0:
        return np.zeros(len(known_encodings))
    dots = known_matrix @ unknown_encoding             # (N,)
    return dots / (norms * unknown_norm)


def _get_all_known_encodings():
    """
    Charge tous les FaceEncoding stockés.
    Retourne (encodings_list, residents_list).
    """
    known_encodings = []
    known_residents = []
    for fe in FaceEncoding.objects.select_related('resident').all():
        try:
            enc = np.array(json.loads(fe.encoding_json), dtype=np.float64)
            known_encodings.append(enc)
            known_residents.append(fe.resident)
        except Exception:
            continue
    return known_encodings, known_residents


# ──────────────────────────────────────────────────────────────
# Vue 1 : Upload de photo + calcul de l'encodage facial
# ──────────────────────────────────────────────────────────────

class ResidentPhotoUploadView(views.APIView):
    """
    POST /api/residents/<resident_id>/photo/
    Multipart : champ 'photo' (image)

    Enregistre la photo et calcule / met à jour l'encodage facial.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, resident_id, *args, **kwargs):
        try:
            resident = Resident.objects.get(pk=resident_id)
        except Resident.DoesNotExist:
            return Response({"error": "Résident introuvable"}, status=status.HTTP_404_NOT_FOUND)

        photo_file = request.FILES.get('photo')
        if not photo_file:
            return Response({"error": "Champ 'photo' manquant"}, status=status.HTTP_400_BAD_REQUEST)

        if not photo_file.content_type.startswith('image/'):
            return Response({"error": "Le fichier doit être une image"}, status=status.HTTP_400_BAD_REQUEST)

        image_bytes = photo_file.read()

        # Calcul de l'encodage AVANT de sauvegarder (pour détecter les erreurs tôt)
        encoding, error = _compute_encoding(image_bytes)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        # Sauvegarde de la photo
        photo_file.seek(0)
        resident.photo.save(photo_file.name, photo_file, save=True)

        # Sauvegarde / mise à jour de l'encodage
        FaceEncoding.objects.update_or_create(
            resident=resident,
            defaults={'encoding_json': json.dumps(encoding.tolist())},
        )

        return Response({
            "success": True,
            "resident_id": resident.id,
            "resident_name": resident.name,
            "photo_url": request.build_absolute_uri(resident.photo.url),
            "message": "Photo et encodage facial enregistrés avec succès",
        }, status=status.HTTP_200_OK)

    def delete(self, request, resident_id, *args, **kwargs):
        """DELETE — supprime la photo et l'encodage."""
        try:
            resident = Resident.objects.get(pk=resident_id)
        except Resident.DoesNotExist:
            return Response({"error": "Résident introuvable"}, status=status.HTTP_404_NOT_FOUND)

        if resident.photo:
            resident.photo.delete(save=True)
        FaceEncoding.objects.filter(resident=resident).delete()

        return Response({"success": True, "message": "Photo et encodage supprimés"})


# ──────────────────────────────────────────────────────────────
# Vue 2 : Liste des résidents (avec URL photo)
# ──────────────────────────────────────────────────────────────

class ResidentListView(views.APIView):
    """
    GET /api/residents/
    Retourne la liste de tous les résidents avec leur photo et statut d'encodage.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        residents = Resident.objects.prefetch_related('face_encoding').all()
        data = []
        for r in residents:
            has_encoding = hasattr(r, 'face_encoding')
            data.append({
                "id": r.id,
                "name": r.name,
                "age": r.age,
                "room_number": r.room_number,
                "risk_level": r.risk_level,
                "photo_url": request.build_absolute_uri(r.photo.url) if r.photo else None,
                "has_face_encoding": has_encoding,
            })
        return Response(data)


# ──────────────────────────────────────────────────────────────
# Vue 3 : Reconnaissance faciale temps réel
# ──────────────────────────────────────────────────────────────

class FaceIdentifyView(views.APIView):
    """
    POST /api/face/identify/
    Body JSON :
      {
        "frame_b64": "<image JPEG encodée en base64>"
      }

    Retourne la liste des visages détectés et, pour chacun, le résident identifié
    (ou null si inconnu).

    Réponse :
      {
        "faces": [
          {
            "location": {"top": .., "right": .., "bottom": .., "left": ..},
            "resident_id": 3,
            "resident_name": "Jean Dupont",
            "confidence": 87.4,
            "photo_url": "http://..."
          },
          {
            "location": {...},
            "resident_id": null,
            "resident_name": "Inconnu",
            "confidence": null,
            "photo_url": null
          }
        ],
        "total_faces": 2,
        "identified": 1
      }
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        face_app = _get_insightface_app()
        if face_app is None:
            return Response(
                {"error": "insightface non disponible sur le serveur"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        frame_b64 = request.data.get('frame_b64')
        if not frame_b64:
            return Response({"error": "Champ 'frame_b64' manquant"}, status=status.HTTP_400_BAD_REQUEST)

        # Décodage de l'image
        try:
            if ',' in frame_b64:
                frame_b64 = frame_b64.split(',', 1)[1]
            image_bytes = base64.b64decode(frame_b64)
            from PIL import Image
            img_pil = Image.open(io.BytesIO(image_bytes))
            # Réduction pour accélérer la détection (max 640px de large)
            max_w = 640
            if img_pil.width > max_w:
                ratio = max_w / img_pil.width
                img_pil = img_pil.resize((max_w, int(img_pil.height * ratio)), Image.LANCZOS)
            img_bgr = _pil_to_bgr(img_pil)
        except Exception as e:
            return Response({"error": f"Image invalide : {e}"}, status=status.HTTP_400_BAD_REQUEST)

        # Détection + encodage des visages dans la frame
        faces = face_app.get(img_bgr)
        if not faces:
            return Response({"faces": [], "total_faces": 0, "identified": 0})

        # Chargement des encodages connus
        known_encodings, known_residents = _get_all_known_encodings()

        results = []
        identified_count = 0

        for face in faces:
            bbox = face.bbox.astype(int)  # [x1, y1, x2, y2]
            left, top, right, bottom = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

            face_data = {
                "location": {"top": top, "right": right, "bottom": bottom, "left": left},
                "resident_id": None,
                "resident_name": "Inconnu",
                "confidence": None,
                "photo_url": None,
            }

            if known_encodings:
                similarities = _cosine_similarities(known_encodings, face.embedding)
                best_idx = int(np.argmax(similarities))
                best_sim = float(similarities[best_idx])

                if best_sim >= FACE_SIMILARITY_THRESHOLD:
                    resident = known_residents[best_idx]
                    confidence = round(best_sim * 100, 1)
                    face_data.update({
                        "resident_id": resident.id,
                        "resident_name": resident.name,
                        "confidence": confidence,
                        "photo_url": (
                            request.build_absolute_uri(resident.photo.url)
                            if resident.photo else None
                        ),
                    })
                    identified_count += 1

            results.append(face_data)

        return Response({
            "faces": results,
            "total_faces": len(results),
            "identified": identified_count,
        })


# ──────────────────────────────────────────────────────────────
# Vue 4 : Statut des encodages (pour le tableau de bord admin)
# ──────────────────────────────────────────────────────────────

class FaceEncodingStatusView(views.APIView):
    """
    GET /api/face/status/
    Retourne la liste des résidents avec leur statut d'encodage facial.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        residents = Resident.objects.prefetch_related('face_encoding').all()
        encoded_ids = set(
            FaceEncoding.objects.values_list('resident_id', flat=True)
        )
        data = {
            "total_residents": residents.count(),
            "with_encoding": len(encoded_ids),
            "without_encoding": residents.count() - len(encoded_ids),
            "residents": [
                {
                    "id": r.id,
                    "name": r.name,
                    "has_photo": bool(r.photo),
                    "has_encoding": r.id in encoded_ids,
                    "photo_url": request.build_absolute_uri(r.photo.url) if r.photo else None,
                }
                for r in residents
            ],
        }
        return Response(data)
