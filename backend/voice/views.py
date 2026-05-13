# import whisper  # Disabled: whisper not installed in venv
# import torch  # Disabled: whisper dependency
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from .models import Shift, ShiftReport
import json
import os

from .models import ShiftReport

# Charge Whisper avec CPU (pas de FP16)
# model = whisper.load_model("base", device="cpu")  # Disabled: whisper not installed
def get_shifts(request):
    """Retourne la liste des shifts actifs"""
    if request.method == 'GET':
        shifts = Shift.objects.filter(is_active=True)
        data = [
            {
                'id': s.id,
                'name': s.name,
                'start_time': s.start_time.strftime('%H:%M'),
                'end_time': s.end_time.strftime('%H:%M'),
                'display_name': f"{s.name} ({s.start_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')})"
            }
            for s in shifts
        ]
        return JsonResponse({'success': True, 'shifts': data})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def create_shift(request):
    """Admin : créer un shift"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            shift = Shift.objects.create(
                name=data['name'],
                start_time=data['start_time'],
                end_time=data['end_time'],
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'success': True, 'shift': {'id': shift.id, 'name': shift.name}})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def update_shift(request, shift_id):
    """Admin : modifier un shift"""
    if request.method == 'PUT':
        try:
            shift = Shift.objects.get(id=shift_id)
            data = json.loads(request.body)
            shift.name = data.get('name', shift.name)
            shift.start_time = data.get('start_time', shift.start_time)
            shift.end_time = data.get('end_time', shift.end_time)
            shift.is_active = data.get('is_active', shift.is_active)
            shift.save()
            return JsonResponse({'success': True})
        except Shift.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Shift not found'}, status=404)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def delete_shift(request, shift_id):
    """Admin : supprimer un shift"""
    if request.method == 'DELETE':
        try:
            shift = Shift.objects.get(id=shift_id)
            shift.delete()
            return JsonResponse({'success': True})
        except Shift.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Shift not found'}, status=404)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def upload_audio(request):
    """Endpoint pour React : reçoit l'audio, transcrit, sauvegarde"""
    if request.method == 'POST':
        try:
            # CHANGEMENT ICI : utiliser shift_id au lieu de shift
            shift_id = request.POST.get('shift_id')
            caregiver_name = request.POST.get('caregiver_name')
            patient_name = request.POST.get('patient_name', '')
            audio_file = request.FILES.get('audio_file')
            
            if not caregiver_name or not audio_file:
                return JsonResponse({
                    'success': False, 
                    'error': 'Missing caregiver_name or audio_file'
                }, status=400)
            
            # CHANGEMENT ICI : récupérer l'objet Shift par son ID
            shift = None
            if shift_id:
                try:
                    shift = Shift.objects.get(id=shift_id)
                    print(f"Shift found: {shift.name}")
                except Shift.DoesNotExist:
                    print(f"Shift with id {shift_id} not found")
            
            # Sauvegarder temporairement
            temp_path = default_storage.save(f'temp_{audio_file.name}', ContentFile(audio_file.read()))
            full_path = os.path.join(settings.MEDIA_ROOT, temp_path)
            
            print(f"Processing audio: {full_path}")
            
            # Transcription avec Whisper (forcer CPU)
            result = model.transcribe(full_path, fp16=False)
            transcription = result['text']
            
            print(f"Transcription: {transcription}")
            
            # Nettoyer fichier temporaire
            os.remove(full_path)
            
            # Sauvegarder en base (shift est maintenant un objet Shift ou None)
            report = ShiftReport.objects.create(
                shift=shift,
                caregiver_name=caregiver_name,
                patient_name=patient_name,
                audio_file=audio_file,
                transcription=transcription,
                summary=transcription
            )
            
            return JsonResponse({
                'success': True,
                'id': report.id,
                'transcription': transcription,
                'message': 'Audio transcrit avec succès'
            })
            
        except Exception as e:
            print(f"Error: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def get_reports(request):
    """Endpoint pour React : récupère tous les rapports"""
    reports = ShiftReport.objects.all().order_by('-created_at')
    data = [
        {
            'id': r.id,
            'shift': r.shift.name if r.shift else 'Unknown',
            'caregiver_name': r.caregiver_name,
            'patient_name': r.patient_name,
            'transcription': r.transcription,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'audio_url': r.audio_file.url if r.audio_file else None
        }
        for r in reports
    ]
    return JsonResponse({'success': True, 'reports': data})

def get_report(request, report_id):
    """Endpoint pour React : récupère un rapport spécifique"""
    try:
        report = ShiftReport.objects.get(id=report_id)
        data = {
            'id': report.id,
            'shift': report.shift.name if report.shift else 'Unknown',
            'caregiver_name': report.caregiver_name,
            'patient_name': report.patient_name,
            'transcription': report.transcription,
            'summary': report.summary,
            'created_at': report.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'audio_url': report.audio_file.url if report.audio_file else None
        }
        return JsonResponse({'success': True, 'report': data})
    except ShiftReport.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Report not found'}, status=404)
@csrf_exempt
def delete_report(request, report_id):
    """Supprimer un rapport"""
    if request.method == 'DELETE':
        try:
            report = ShiftReport.objects.get(id=report_id)
            report.delete()
            return JsonResponse({'success': True, 'message': 'Report deleted'})
        except ShiftReport.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Report not found'}, status=404)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def update_transcription(request, report_id):
    """Admin : corriger la transcription d'un rapport"""
    if request.method == 'PUT':
        try:
            report = ShiftReport.objects.get(id=report_id)
            data = json.loads(request.body)
            new_transcription = data.get('transcription')
            
            if new_transcription:
                report.transcription = new_transcription
                report.summary = new_transcription
                report.save()
                return JsonResponse({'success': True, 'message': 'Transcription updated'})
            return JsonResponse({'success': False, 'error': 'No transcription provided'}, status=400)
        except ShiftReport.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Report not found'}, status=404)
    return JsonResponse({'error': 'Method not allowed'}, status=405)