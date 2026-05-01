"""
AuraCare — Add Medications Script
Run from backend folder:
    py add_medications.py
"""

import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from core.models import Resident, Medication

MEDICATIONS = [
    # Alice Abernathy
    { 'resident': 'Alice Abernathy', 'name': 'Amlodipine', 'dosage': '5mg',   'frequency': 'once_daily',  'time1': '08:00' },
    { 'resident': 'Alice Abernathy', 'name': 'Metformin',  'dosage': '500mg', 'frequency': 'twice_daily', 'time1': '08:00', 'time2': '20:00' },
    { 'resident': 'Alice Abernathy', 'name': 'Aspirin',    'dosage': '100mg', 'frequency': 'once_daily',  'time1': '12:00' },

    # John Smith
    { 'resident': 'John Smith', 'name': 'Atorvastatin', 'dosage': '20mg', 'frequency': 'once_daily', 'time1': '21:00' },
    { 'resident': 'John Smith', 'name': 'Lisinopril',   'dosage': '10mg', 'frequency': 'once_daily', 'time1': '08:00' },

    # Eleanor Rigby
    { 'resident': 'Eleanor Rigby', 'name': 'Donepezil', 'dosage': '5mg',  'frequency': 'once_daily', 'time1': '21:00' },
    { 'resident': 'Eleanor Rigby', 'name': 'Sertraline', 'dosage': '50mg', 'frequency': 'once_daily', 'time1': '08:00' },
    # Margaret Hamilton
    { 'resident': 'Margaret Hamilton', 'name': 'Warfarin',    'dosage': '2mg',    'frequency': 'once_daily',       'time1': '17:00' },
    { 'resident': 'Margaret Hamilton', 'name': 'Furosemide',  'dosage': '40mg',   'frequency': 'once_daily',       'time1': '08:00' },

    # George Washington
    { 'resident': 'George Washington', 'name': 'Omeprazole',  'dosage': '20mg',   'frequency': 'once_daily',       'time1': '07:00' },
    { 'resident': 'George Washington', 'name': 'Vitamin D',   'dosage': '1000IU', 'frequency': 'once_daily',       'time1': '08:00' },

    # Robert Chase
    { 'resident': 'Robert Chase',      'name': 'Metoprolol',  'dosage': '25mg',   'frequency': 'twice_daily',      'time1': '08:00', 'time2': '20:00' },
    { 'resident': 'Robert Chase',      'name': 'Gabapentin',  'dosage': '300mg',  'frequency': 'three_times_daily','time1': '08:00', 'time2': '14:00', 'time3': '20:00' },

    # Martha Stewart
    { 'resident': 'Martha Stewart',    'name': 'Levothyroxine','dosage': '50mcg', 'frequency': 'once_daily',       'time1': '07:00' },
    { 'resident': 'Martha Stewart',    'name': 'Calcium',     'dosage': '500mg',  'frequency': 'twice_daily',      'time1': '08:00', 'time2': '20:00' },

    # Thomas Edison
    { 'resident': 'Thomas Edison',     'name': 'Levodopa',    'dosage': '100mg',  'frequency': 'three_times_daily','time1': '08:00', 'time2': '13:00', 'time3': '18:00' },
    { 'resident': 'Thomas Edison',     'name': 'Rivastigmine','dosage': '3mg',    'frequency': 'twice_daily',      'time1': '08:00', 'time2': '20:00' },

    # Rosa Parks
    { 'resident': 'Rosa Parks',        'name': 'Alendronate', 'dosage': '70mg',   'frequency': 'weekly',           'time1': '08:00' },
    { 'resident': 'Rosa Parks',        'name': 'Ramipril',    'dosage': '5mg',    'frequency': 'once_daily',       'time1': '08:00' },
]

print("=" * 50)
print("  AuraCare — Adding Medications")
print("=" * 50)

created = 0
skipped = 0

for med in MEDICATIONS:
    resident = Resident.objects.filter(name=med['resident']).first()
    if not resident:
        print(f"  ❌ Resident not found: {med['resident']}")
        skipped += 1
        continue

    # Skip if already exists
    if Medication.objects.filter(resident=resident, name=med['name']).exists():
        print(f"  ⏭️  Already exists: {med['resident']} — {med['name']}")
        skipped += 1
        continue

    Medication.objects.create(
        resident=resident,
        name=med['name'],
        dosage=med.get('dosage', ''),
        frequency=med['frequency'],
        scheduled_time=med['time1'],
        scheduled_time_2=med.get('time2'),
        scheduled_time_3=med.get('time3'),
        is_active=True,
    )
    print(f"  ✅ Added: {med['resident']} — {med['name']} {med['dosage']} ({med['frequency']})")
    created += 1

print(f"\n  Created: {created} medications")
print(f"  Skipped: {skipped}")
print("=" * 50)
