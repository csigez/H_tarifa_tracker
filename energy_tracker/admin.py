from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html
from .models import TariffConfig, MeterReading


@admin.register(TariffConfig)
class TariffConfigAdmin(admin.ModelAdmin):
    """Admin interface for TariffConfig singleton"""
    list_display = ['winter_price', 'summer_price_low', 'summer_price_high', 'summer_threshold']
    fieldsets = (
        ('Winter Pricing', {
            'fields': ('winter_price',)
        }),
        ('Summer Tiered Pricing', {
            'fields': ('summer_price_low', 'summer_price_high', 'summer_threshold'),
            'description': 'Configure tiered pricing for summer usage. Low price applies below threshold, high price applies above threshold.'
        }),
    )
    
    def has_add_permission(self, request):
        # Prevent adding multiple instances
        return not TariffConfig.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the singleton
        return False


@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    """Admin interface for MeterReading with detailed cost breakdown"""
    list_display = [
        'reading_date', 'summer_value', 'winter_value', 
        'summer_usage', 'winter_usage', 'total_cost', 'quota_indicator'
    ]
    list_filter = ['reading_date']
    search_fields = ['reading_date']
    readonly_fields = [
        'summer_usage', 'winter_usage', 'total_cost',
        'locked_winter_price', 'locked_summer_price_low', 
        'locked_summer_price_high', 'locked_summer_threshold',
        'cost_breakdown', 'quota_status'
    ]
    date_hierarchy = 'reading_date'
    
    fieldsets = (
        ('Reading Input', {
            'fields': ('reading_date', 'summer_value', 'winter_value')
        }),
        ('Calculated Usage', {
            'fields': ('summer_usage', 'winter_usage'),
            'classes': ('collapse',)
        }),
        ('Cost Calculation', {
            'fields': ('total_cost', 'cost_breakdown'),
            'classes': ('collapse',)
        }),
        ('Snapshotted Pricing (Historical Record)', {
            'fields': (
                'locked_winter_price', 'locked_summer_price_low',
                'locked_summer_price_high', 'locked_summer_threshold'
            ),
            'classes': ('collapse',)
        }),
        ('Quota Status', {
            'fields': ('quota_status',),
            'classes': ('collapse',)
        }),
    )
    
    def cost_breakdown(self, obj):
        """Display detailed cost breakdown"""
        if not obj.pk:
            return "Save reading to calculate costs"
        
        winter_cost = obj.winter_usage * obj.locked_winter_price
        summer_cost = obj.total_cost - winter_cost
        
        return format_html(
            '<div style="font-family: monospace;">'
            '<div>Winter: {} kWh × {} = {} Ft</div>'
            '<div>Summer: {} kWh = {} Ft</div>'
            '<div><strong>Total: {} Ft</strong></div>'
            '</div>',
            obj.winter_usage, obj.locked_winter_price, f"{winter_cost:.2f}",
            obj.summer_usage, f"{summer_cost:.2f}",
            f"{obj.total_cost:.2f}"
        )
    cost_breakdown.short_description = 'Cost Breakdown'
    
    def quota_status(self, obj):
        """Display summer quota usage status"""
        if not obj.pk:
            return "Save reading to calculate quota status"
        
        cumulative = obj.get_yearly_cumulative_summer_usage()
        threshold = obj.locked_summer_threshold
        percentage = obj.get_quota_usage_percentage()
        
        # Determine color based on usage
        if percentage < 70:
            color = 'green'
        elif percentage < 90:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<div>'
            '<div style="margin-bottom: 5px;">'
            '<strong>Summer Quota Usage:</strong><br>'
            '{} / {} kWh ({}%)'
            '</div>'
            '<div style="background: #ddd; border-radius: 3px; overflow: hidden; height: 20px;">'
            '<div style="background: {}; width: {}%; height: 100%; transition: width 0.3s;"></div>'
            '</div>'
            '</div>',
            cumulative, threshold, f"{percentage:.1f}",
            color, f"{percentage:.1f}"
        )
    quota_status.short_description = 'Summer Quota Status'
    
    def quota_indicator(self, obj):
        """Compact quota indicator for list view"""
        if not obj.pk:
            return "—"
        
        percentage = obj.get_quota_usage_percentage()
        cumulative = obj.get_yearly_cumulative_summer_usage()
        
        if percentage < 70:
            color = 'green'
            symbol = '✓'
        elif percentage < 90:
            color = 'orange'
            symbol = '⚠'
        else:
            color = 'red'
            symbol = '✗'
        
        return format_html(
            '<span style="color: {0};">{1} {2:.0f}%</span>',
            color, symbol, percentage
        )
    quota_indicator.short_description = 'Quota'
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-reading_date')


# Customize admin site header and title
admin.site.site_header = 'H-Tariff Tracker Administration'
admin.site.site_title = 'H-Tariff Tracker'
admin.site.index_title = 'Energy Usage and Cost Tracking'
