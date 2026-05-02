from django.db import models

# Create your models here.

class Shift(models.Model):
    """Modèle pour les shifts configurables par l'admin"""
    name = models.CharField(max_length=50)  # ex: "Morning", "Afternoon", "Night"
    start_time = models.TimeField()         # ex: 06:00
    end_time = models.TimeField()           # ex: 14:00
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"
    
    class Meta:
        ordering = ['start_time']


class ShiftReport(models.Model):
    """Modèle pour les rapports de shift handover"""
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    caregiver_name = models.CharField(max_length=100)
    patient_name = models.CharField(max_length=100, blank=True)
    audio_file = models.FileField(upload_to='audios/')
    transcription = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        shift_name = self.shift.name if self.shift else 'Unknown'
        return f"{self.caregiver_name} - {shift_name}"
    
    @property
    def shift_display(self):
        """Retourne le nom du shift pour l'affichage"""
        if self.shift:
            return f"{self.shift.name} ({self.shift.start_time.strftime('%H:%M')} - {self.shift.end_time.strftime('%H:%M')})"
        return 'Unknown'