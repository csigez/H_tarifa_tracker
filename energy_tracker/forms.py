from django import forms
from django.utils import timezone
from .models import MeterReading


class MeterReadingForm(forms.ModelForm):
    """Form for creating meter readings with validation"""
    
    class Meta:
        model = MeterReading
        fields = ['reading_date', 'summer_value', 'winter_value']
        widgets = {
            'reading_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),
            'summer_value': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Enter summer register value',
                    'min': '0'
                }
            ),
            'winter_value': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Enter winter register value',
                    'min': '0'
                }
            ),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reading_date'].widget.attrs['max'] = timezone.now().date().strftime('%Y-%m-%d')

        # Set default date to today
        if not self.instance.pk and 'reading_date' not in self.initial:
            self.initial['reading_date'] = timezone.now().date()
        
        # Add Bootstrap classes and placeholders
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if not field.widget.attrs.get('placeholder'):
                field.widget.attrs['placeholder'] = field.label
    
    def clean_summer_value(self):
        """Validate summer value is non-negative"""
        summer_value = self.cleaned_data.get('summer_value')
        if summer_value is not None and summer_value < 0:
            raise forms.ValidationError("Summer value cannot be negative.")
        return summer_value
    
    def clean_winter_value(self):
        """Validate winter value is non-negative"""
        winter_value = self.cleaned_data.get('winter_value')
        if winter_value is not None and winter_value < 0:
            raise forms.ValidationError("Winter value cannot be negative.")
        return winter_value
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        reading_date = cleaned_data.get('reading_date')
        summer_value = cleaned_data.get('summer_value')
        winter_value = cleaned_data.get('winter_value')
        
        # Check for duplicate readings on the same date
        if reading_date and MeterReading.objects.filter(
            reading_date=reading_date
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                f"A meter reading already exists for {reading_date}. "
                "Please choose a different date or edit the existing reading."
            )
        
        # Validate against previous reading to prevent negative consumption
        if reading_date and summer_value is not None and winter_value is not None:
            previous_reading = MeterReading.objects.filter(
                reading_date__lt=reading_date
            ).order_by('-reading_date').first()
            
            if previous_reading:
                if summer_value < previous_reading.summer_value:
                    raise forms.ValidationError(
                        f"Summer value ({summer_value}) cannot be less than previous reading ({previous_reading.summer_value}) "
                        f"from {previous_reading.reading_date}. This would result in negative consumption."
                    )
                if winter_value < previous_reading.winter_value:
                    raise forms.ValidationError(
                        f"Winter value ({winter_value}) cannot be less than previous reading ({previous_reading.winter_value}) "
                        f"from {previous_reading.reading_date}. This would result in negative consumption."
                    )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to handle calculation logic"""
        instance = super().save(commit=False)
        
        # The model's save method will handle calculations
        if commit:
            instance.save()
        
        return instance
