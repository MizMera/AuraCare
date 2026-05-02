from django import forms
from .models import ShiftReport

class ShiftReportForm(forms.ModelForm):
    class Meta:
        model = ShiftReport
        fields = ['shift', 'caregiver_name', 'patient_name', 'audio_file']