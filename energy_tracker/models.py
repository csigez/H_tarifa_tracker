from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError


class TariffConfig(models.Model):
    """Singleton model for storing tariff configuration"""
    winter_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per kWh for winter season")
    summer_price_low = models.DecimalField(max_digits=10, decimal_places=2, help_text="Discounted price below quota")
    summer_price_high = models.DecimalField(max_digits=10, decimal_places=2, help_text="Market price above quota")
    summer_threshold = models.IntegerField(help_text="Yearly summer quota threshold in kWh")
    
    class Meta:
        verbose_name = "Tariff Configuration"
        verbose_name_plural = "Tariff Configuration"
    
    def clean(self):
        if TariffConfig.objects.exists() and not self.pk:
            raise ValidationError("Only one TariffConfig instance can exist.")
        if self.summer_price_low >= self.summer_price_high:
            raise ValidationError("Summer low price must be less than summer high price.")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Get the singleton configuration instance"""
        config, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'winter_price': Decimal('40.00'),
                'summer_price_low': Decimal('36.00'),
                'summer_price_high': Decimal('70.00'),
                'summer_threshold': 2523,
            }
        )
        return config
    
    def __str__(self):
        return f"Tariff Config (Winter: {self.winter_price}, Summer Low: {self.summer_price_low}, Summer High: {self.summer_price_high})"


class MeterReading(models.Model):
    """Model for storing meter readings with tiered pricing calculations"""
    reading_date = models.DateField()
    summer_value = models.IntegerField(help_text="Summer register reading")
    winter_value = models.IntegerField(help_text="Winter register reading")
    
    # Calculated fields
    summer_usage = models.IntegerField(editable=False, help_text="Calculated summer usage delta")
    winter_usage = models.IntegerField(editable=False, help_text="Calculated winter usage delta")
    
    # Snapshotted pricing (immutable history)
    locked_winter_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    locked_summer_price_low = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    locked_summer_price_high = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    locked_summer_threshold = models.IntegerField(editable=False)
    
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    class Meta:
        ordering = ['-reading_date']
        verbose_name = "Meter Reading"
        verbose_name_plural = "Meter Readings"
    
    def clean(self):
        # Check for duplicate readings on the same date
        if MeterReading.objects.filter(reading_date=self.reading_date).exclude(pk=self.pk).exists():
            raise ValidationError("A reading for this date already exists.")
        
        # Ensure values are non-negative and summer >= winter (typical for H-tariff)
        if self.summer_value is not None and self.summer_value < 0:
            raise ValidationError("Summer value cannot be negative.")
        if self.winter_value is not None and self.winter_value < 0:
            raise ValidationError("Winter value cannot be negative.")
        
        # Validate against previous reading to prevent negative consumption
        previous_reading = MeterReading.objects.filter(
            reading_date__lt=self.reading_date
        ).order_by('-reading_date').first()
        
        if previous_reading:
            if self.summer_value is not None and self.summer_value < previous_reading.summer_value:
                raise ValidationError(
                    f"Summer value ({self.summer_value}) cannot be less than previous reading ({previous_reading.summer_value}). "
                    f"This would result in negative consumption."
                )
            if self.winter_value is not None and self.winter_value < previous_reading.winter_value:
                raise ValidationError(
                    f"Winter value ({self.winter_value}) cannot be less than previous reading ({previous_reading.winter_value}). "
                    f"This would result in negative consumption."
                )
    
    def save(self, *args, **kwargs):
        self.clean()
        
        # Get current tariff configuration and snapshot it
        config = TariffConfig.get_config()
        self.locked_winter_price = config.winter_price
        self.locked_summer_price_low = config.summer_price_low
        self.locked_summer_price_high = config.summer_price_high
        self.locked_summer_threshold = config.summer_threshold
        
        # Calculate usage deltas
        previous_reading = MeterReading.objects.filter(
            reading_date__lt=self.reading_date
        ).order_by('-reading_date').first()
        
        if previous_reading:
            self.summer_usage = self.summer_value - previous_reading.summer_value
            self.winter_usage = self.winter_value - previous_reading.winter_value
        else:
            # First reading - assume zero usage
            self.summer_usage = self.summer_value
            self.winter_usage = self.winter_value
        
        # Calculate costs using tiered pricing logic
        self.total_cost = self._calculate_total_cost()
        
        super().save(*args, **kwargs)
    
    def _calculate_total_cost(self):
        """Calculate total cost using tiered summer pricing logic"""
        # Winter cost is straightforward
        winter_cost = self.winter_usage * self.locked_winter_price
        
        # Summer cost requires tiered logic
        summer_cost = self._calculate_summer_cost()
        
        return winter_cost + summer_cost
    
    def _calculate_summer_cost(self):
        """Calculate summer cost using tiered pricing with quota threshold"""
        if self.summer_usage <= 0:
            return Decimal('0.00')
        
        # Get cumulative summer usage for the current year before this reading
        year_start = self.reading_date.replace(month=1, day=1)
        previous_year_readings = MeterReading.objects.filter(
            reading_date__year=self.reading_date.year,
            reading_date__lt=self.reading_date
        ).order_by('reading_date')
        
        cumulative_usage = sum(reading.summer_usage for reading in previous_year_readings)
        
        # Apply tiered pricing logic
        threshold = self.locked_summer_threshold
        low_price = self.locked_summer_price_low
        high_price = self.locked_summer_price_high
        
        # Case A: Fully below threshold
        if cumulative_usage + self.summer_usage <= threshold:
            return Decimal(self.summer_usage) * low_price
        
        # Case B: Fully above threshold
        elif cumulative_usage >= threshold:
            return Decimal(self.summer_usage) * high_price
        
        # Case C: Crossing threshold - split calculation
        else:
            remaining_quota = threshold - cumulative_usage
            low_usage = remaining_quota
            high_usage = self.summer_usage - remaining_quota
            
            low_cost = Decimal(low_usage) * low_price
            high_cost = Decimal(high_usage) * high_price
            
            return low_cost + high_cost
    
    def get_yearly_cumulative_summer_usage(self):
        """Get cumulative summer usage for the current year including this reading"""
        year_start = self.reading_date.replace(month=1, day=1)
        year_readings = MeterReading.objects.filter(
            reading_date__year=self.reading_date.year,
            reading_date__lte=self.reading_date
        ).order_by('reading_date')
        
        return sum(reading.summer_usage for reading in year_readings)
    
    def get_quota_usage_percentage(self):
        """Get percentage of summer quota used"""
        if not self.locked_summer_threshold:
            return 0
        cumulative = self.get_yearly_cumulative_summer_usage()
        return min(100, (cumulative / self.locked_summer_threshold) * 100)
    
    def __str__(self):
        return f"Reading {self.reading_date} (Summer: {self.summer_value}, Winter: {self.winter_value})"
