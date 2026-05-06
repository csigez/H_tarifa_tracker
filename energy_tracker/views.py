from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from .models import MeterReading, TariffConfig
from .forms import MeterReadingForm


class DashboardView(ListView):
    """Main dashboard showing energy usage overview and quota status"""
    model = MeterReading
    template_name = 'energy_tracker/dashboard.html'
    context_object_name = 'recent_readings'
    paginate_by = 10
    
    def get_queryset(self):
        return MeterReading.objects.order_by('-reading_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current tariff configuration
        config = TariffConfig.get_config()
        context['config'] = config
        
        # Get current year statistics
        current_year = timezone.now().year
        year_readings = MeterReading.objects.filter(reading_date__year=current_year)
        
        if year_readings.exists():
            # Calculate yearly totals
            total_summer_usage = year_readings.aggregate(Sum('summer_usage'))['summer_usage__sum'] or 0
            total_winter_usage = year_readings.aggregate(Sum('winter_usage'))['winter_usage__sum'] or 0
            total_cost = year_readings.aggregate(Sum('total_cost'))['total_cost__sum'] or 0
            
            context['year_stats'] = {
                'summer_usage': total_summer_usage,
                'winter_usage': total_winter_usage,
                'total_cost': total_cost,
                'quota_used': total_summer_usage,
                'quota_remaining': max(0, config.summer_threshold - total_summer_usage),
                'quota_percentage': min(100, (total_summer_usage / config.summer_threshold) * 100) if config.summer_threshold > 0 else 0,
            }
            
            # Get latest reading for current values
            latest_reading = year_readings.order_by('-reading_date').first()
            if latest_reading:
                context['latest_reading'] = latest_reading
                context['current_summer_value'] = latest_reading.summer_value
                context['current_winter_value'] = latest_reading.winter_value
        else:
            context['year_stats'] = {
                'summer_usage': 0,
                'winter_usage': 0,
                'total_cost': 0,
                'quota_used': 0,
                'quota_remaining': config.summer_threshold,
                'quota_percentage': 0,
            }
        
        return context


class MeterReadingCreateView(CreateView):
    """Create new meter reading"""
    model = MeterReading
    form_class = MeterReadingForm
    template_name = 'energy_tracker/reading_form.html'
    success_url = reverse_lazy('energy_tracker:dashboard')
    
    def form_valid(self, form):
        messages.success(self.request, 'Meter reading saved successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get previous reading for reference
        previous_reading = MeterReading.objects.order_by('-reading_date').first()
        if previous_reading:
            context['previous_reading'] = previous_reading
            context['suggested_summer'] = previous_reading.summer_value
            context['suggested_winter'] = previous_reading.winter_value
        
        return context


class MeterReadingDetailView(DetailView):
    """Detailed view of a meter reading"""
    model = MeterReading
    template_name = 'energy_tracker/reading_detail.html'
    context_object_name = 'reading'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get previous and next readings for comparison
        reading = self.object
        
        previous_reading = MeterReading.objects.filter(
            reading_date__lt=reading.reading_date
        ).order_by('-reading_date').first()
        
        next_reading = MeterReading.objects.filter(
            reading_date__gt=reading.reading_date
        ).order_by('reading_date').first()
        
        context['previous_reading'] = previous_reading
        context['next_reading'] = next_reading
        
        return context


def add_reading(request):
    """Function-based view for adding readings (alternative to class-based)"""
    previous_reading = MeterReading.objects.order_by('-reading_date').first()

    if request.method == 'POST':
        form = MeterReadingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Meter reading added successfully!')
            return redirect('energy_tracker:dashboard')
    else:
        form = MeterReadingForm()
        if previous_reading:
            form.initial['summer_value'] = previous_reading.summer_value
            form.initial['winter_value'] = previous_reading.winter_value

    return render(request, 'energy_tracker/reading_form.html', {
        'form': form,
        'previous_reading': previous_reading,
    })
