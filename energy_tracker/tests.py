from django.test import TestCase
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.contrib.admin.sites import AdminSite
from decimal import Decimal
from datetime import date, timedelta
from .models import MeterReading, TariffConfig
from .forms import MeterReadingForm
from .admin import MeterReadingAdmin, TariffConfigAdmin
from .templatetags.math_filters import mul, sub, div


class MeterReadingTestCase(TestCase):
    """Test cases for MeterReading model following the PRD requirements"""
    
    def setUp(self):
        """Set up test data"""
        # Create default tariff configuration
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 2500
        self.config.save()
    
    def test_first_reading_handling(self):
        """
        PRD Test Case 1: Add a reading to an empty DB. Assert no crash, consumption = 0.
        """
        # Clear any existing data
        MeterReading.objects.all().delete()
        
        # Add first reading
        reading = MeterReading.objects.create(
            reading_date=date(2024, 1, 1),
            summer_value=1000,
            winter_value=500
        )
        
        # Assert no crash and consumption equals the initial values
        self.assertEqual(reading.summer_usage, 1000)  # First reading: usage = value
        self.assertEqual(reading.winter_usage, 500)   # First reading: usage = value
        self.assertIsNotNone(reading.total_cost)
        self.assertGreater(reading.total_cost, 0)
    
    def test_simple_consumption(self):
        """
        PRD Test Case 2: Add Reading A (1000) and Reading B (1100). Assert Consumption = 100.
        """
        # Clear any existing data
        MeterReading.objects.all().delete()
        
        # Add Reading A
        reading_a = MeterReading.objects.create(
            reading_date=date(2024, 1, 1),
            summer_value=1000,
            winter_value=500
        )
        
        # Add Reading B
        reading_b = MeterReading.objects.create(
            reading_date=date(2024, 2, 1),
            summer_value=1100,
            winter_value=600
        )
        
        # Assert consumption calculation
        self.assertEqual(reading_b.summer_usage, 100)  # 1100 - 1000
        self.assertEqual(reading_b.winter_usage, 100)  # 600 - 500
    
    def test_tiered_pricing_split(self):
        """
        PRD Test Case 3: Test quota crossing logic.
        Set Threshold = 2500, Previous Cumulative = 2480, Add Reading with Delta = 50.
        Assert that 20 units are calculated at Low Price, and 30 units at High Price.
        """
        # Clear any existing data and set threshold
        MeterReading.objects.all().delete()
        self.config.summer_threshold = 2500
        self.config.save()
        
        # Create previous readings to establish cumulative usage of 2480
        cumulative_reading = MeterReading.objects.create(
            reading_date=date(2024, 1, 1),
            summer_value=2480,
            winter_value=1000
        )
        
        # Add new reading with delta of 50 (total will be 2530)
        new_reading = MeterReading.objects.create(
            reading_date=date(2024, 2, 1),
            summer_value=2530,  # 2480 + 50
            winter_value=1100
        )
        
        # Calculate expected costs
        # 20 units at low price (36.00) + 30 units at high price (70.00)
        expected_low_cost = Decimal(20) * Decimal('36.00')
        expected_high_cost = Decimal(30) * Decimal('70.00')
        expected_summer_cost = expected_low_cost + expected_high_cost
        expected_winter_cost = Decimal(100) * Decimal('40.00')  # winter usage
        expected_total_cost = expected_summer_cost + expected_winter_cost
        
        # Assert the calculation is correct
        self.assertEqual(new_reading.summer_usage, 50)
        self.assertEqual(new_reading.total_cost, expected_total_cost)
        
        # Verify the split calculation manually
        summer_cost = new_reading._calculate_summer_cost()
        self.assertEqual(summer_cost, expected_summer_cost)
    
    def test_price_change_isolation(self):
        """
        PRD Test Case 4: Create a reading with Price A, update Global Config to Price B,
        assert the reading's cost remains calculated with Price A.
        """
        # Clear any existing data
        MeterReading.objects.all().delete()
        
        # Set initial prices (Price A)
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.save()
        
        # Create reading with Price A
        reading = MeterReading.objects.create(
            reading_date=date(2024, 1, 1),
            summer_value=1000,
            winter_value=500
        )
        
        # Store the original cost
        original_cost = reading.total_cost
        original_winter_price = reading.locked_winter_price
        original_summer_low_price = reading.locked_summer_price_low
        original_summer_high_price = reading.locked_summer_price_high
        
        # Update global config to Price B
        self.config.winter_price = Decimal('50.00')
        self.config.summer_price_low = Decimal('45.00')
        self.config.summer_price_high = Decimal('80.00')
        self.config.save()
        
        # Refresh the reading from database
        reading.refresh_from_db()
        
        # Assert the reading's cost and locked prices remain unchanged
        self.assertEqual(reading.total_cost, original_cost)
        self.assertEqual(reading.locked_winter_price, original_winter_price)
        self.assertEqual(reading.locked_summer_price_low, original_summer_low_price)
        self.assertEqual(reading.locked_summer_price_high, original_summer_high_price)
    
    def test_negative_consumption_validation(self):
        """
        Additional Test: Verify that negative consumption is properly handled.
        This test should now pass with the validation fix implemented.
        """
        # Clear any existing data
        MeterReading.objects.all().delete()
        
        # Create initial reading
        reading1 = MeterReading.objects.create(
            reading_date=date(2024, 1, 1),
            summer_value=1000,
            winter_value=500
        )
        
        # Attempt to create reading with lower values should now raise ValidationError
        with self.assertRaises(ValidationError) as context:
            MeterReading.objects.create(
                reading_date=date(2024, 2, 1),
                summer_value=900,  # Lower than previous (1000) - should cause negative consumption
                winter_value=400   # Lower than previous (500) - should cause negative consumption
            )
        
        # Verify the error message mentions negative consumption
        error_message = str(context.exception)
        self.assertIn("cannot be less than previous reading", error_message)
        self.assertIn("negative consumption", error_message)
    
    def test_fully_below_threshold_pricing(self):
        """
        Additional Test: Verify pricing when fully below threshold.
        """
        # Clear any existing data
        MeterReading.objects.all().delete()
        
        # Create reading with usage well below threshold
        reading = MeterReading.objects.create(
            reading_date=date(2024, 1, 1),
            summer_value=100,  # Well below 2500 threshold
            winter_value=50
        )
        
        # Should be charged entirely at low price
        expected_summer_cost = Decimal(100) * Decimal('36.00')
        expected_winter_cost = Decimal(50) * Decimal('40.00')
        expected_total_cost = expected_summer_cost + expected_winter_cost
        
        self.assertEqual(reading.total_cost, expected_total_cost)
    
    def test_fully_above_threshold_pricing(self):
        """
        Additional Test: Verify pricing when fully above threshold.
        """
        # Clear any existing data
        MeterReading.objects.all().delete()
        
        # Create reading that puts us well above threshold
        cumulative_reading = MeterReading.objects.create(
            reading_date=date(2024, 1, 1),
            summer_value=2600,  # Above 2500 threshold
            winter_value=1000
        )
        
        # Add another reading - should be entirely at high price
        new_reading = MeterReading.objects.create(
            reading_date=date(2024, 2, 1),
            summer_value=2700,  # Additional 100, all at high price
            winter_value=1100
        )
        
        # Should be charged entirely at high price for summer usage
        expected_summer_cost = Decimal(100) * Decimal('70.00')  # High price
        expected_winter_cost = Decimal(100) * Decimal('40.00')
        expected_total_cost = expected_summer_cost + expected_winter_cost
        
        self.assertEqual(new_reading.total_cost, expected_total_cost)


class TariffConfigTestCase(TestCase):
    """Test cases for TariffConfig model"""
    
    def test_singleton_behavior(self):
        """Test that only one TariffConfig instance can exist"""
        config1 = TariffConfig.get_config()
        config2 = TariffConfig.get_config()
        
        self.assertEqual(config1.pk, config2.pk)
        
        # Attempt to create second instance should raise ValidationError
        with self.assertRaises(ValidationError):
            TariffConfig.objects.create(
                winter_price=Decimal('50.00'),
                summer_price_low=Decimal('40.00'),
                summer_price_high=Decimal('80.00'),
                summer_threshold=3000
            )
    
    def test_price_validation(self):
        """Test that low price must be less than high price"""
        config = TariffConfig.get_config()
        
        # Attempt to set low price >= high price should raise ValidationError
        config.summer_price_low = Decimal('80.00')
        config.summer_price_high = Decimal('70.00')

        with self.assertRaises(ValidationError):
            config.save()


class CascadeRecalculationTestCase(TestCase):
    """Test cases for automatic recalculation of subsequent readings on edit"""

    def setUp(self):
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 2500
        self.config.save()
        MeterReading.objects.all().delete()

    def test_editing_first_reading_recalculates_subsequent_usage_and_cost(self):
        """Editing the first reading should ripple through later readings' deltas and costs."""
        reading_a = MeterReading.objects.create(
            reading_date=date(2024, 1, 1), summer_value=100, winter_value=50
        )
        reading_b = MeterReading.objects.create(
            reading_date=date(2024, 2, 1), summer_value=250, winter_value=120
        )
        reading_c = MeterReading.objects.create(
            reading_date=date(2024, 3, 1), summer_value=400, winter_value=200
        )

        reading_a.summer_value = 80
        reading_a.winter_value = 40
        reading_a.save()

        reading_a.refresh_from_db()
        reading_b.refresh_from_db()
        reading_c.refresh_from_db()

        # The edited first reading still reports usage equal to its raw value
        self.assertEqual(reading_a.summer_usage, 80)
        self.assertEqual(reading_a.winter_usage, 40)

        # B's deltas are now computed against the edited A
        self.assertEqual(reading_b.summer_usage, 250 - 80)
        self.assertEqual(reading_b.winter_usage, 120 - 40)
        self.assertEqual(
            reading_b.total_cost,
            Decimal(170) * Decimal('36.00') + Decimal(80) * Decimal('40.00')
        )

        # C's deltas are relative to B (whose raw values were untouched) and stay the same
        self.assertEqual(reading_c.summer_usage, 400 - 250)
        self.assertEqual(reading_c.winter_usage, 200 - 120)
        self.assertEqual(
            reading_c.total_cost,
            Decimal(150) * Decimal('36.00') + Decimal(80) * Decimal('40.00')
        )

    def test_skip_cascade_flag_prevents_recalculation_of_subsequent_readings(self):
        """Saving with _skip_cascade=True must not trigger the recalculation cascade."""
        reading_a = MeterReading.objects.create(
            reading_date=date(2024, 1, 1), summer_value=100, winter_value=50
        )
        reading_b = MeterReading.objects.create(
            reading_date=date(2024, 2, 1), summer_value=250, winter_value=120
        )
        original_b_summer_usage = reading_b.summer_usage
        original_b_total_cost = reading_b.total_cost

        reading_a.summer_value = 80
        reading_a.winter_value = 40
        reading_a.save(_skip_cascade=True)

        reading_b.refresh_from_db()
        self.assertEqual(reading_b.summer_usage, original_b_summer_usage)
        self.assertEqual(reading_b.total_cost, original_b_total_cost)

    def test_cascade_relocks_subsequent_readings_to_current_tariff_prices(self):
        """
        Cascade recalculation re-snapshots prices from the *current* TariffConfig,
        so changing prices and then editing an earlier reading also changes the
        locked prices of later readings (documents current behavior).
        """
        reading_a = MeterReading.objects.create(
            reading_date=date(2024, 1, 1), summer_value=100, winter_value=50
        )
        reading_b = MeterReading.objects.create(
            reading_date=date(2024, 2, 1), summer_value=250, winter_value=120
        )
        original_locked_winter_price = reading_b.locked_winter_price

        self.config.winter_price = Decimal('99.00')
        self.config.save()

        # Re-saving A triggers the cascade, which re-locks B's prices to the new config
        reading_a.save()
        reading_b.refresh_from_db()

        self.assertNotEqual(reading_b.locked_winter_price, original_locked_winter_price)
        self.assertEqual(reading_b.locked_winter_price, Decimal('99.00'))


class ModelHelperMethodsTestCase(TestCase):
    """Test cases for MeterReading helper methods used by templates and admin"""

    def setUp(self):
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 300
        self.config.save()
        MeterReading.objects.all().delete()

    def test_get_yearly_cumulative_summer_usage(self):
        reading_a = MeterReading.objects.create(
            reading_date=date(2024, 1, 1), summer_value=100, winter_value=50
        )
        reading_b = MeterReading.objects.create(
            reading_date=date(2024, 2, 1), summer_value=180, winter_value=80
        )

        self.assertEqual(reading_a.get_yearly_cumulative_summer_usage(), 100)
        self.assertEqual(reading_b.get_yearly_cumulative_summer_usage(), 100 + 80)

    def test_get_quota_usage_percentage(self):
        reading = MeterReading.objects.create(
            reading_date=date(2024, 1, 1), summer_value=150, winter_value=50
        )
        self.assertEqual(reading.get_quota_usage_percentage(), 50.0)

    def test_get_quota_usage_percentage_caps_at_100(self):
        reading = MeterReading.objects.create(
            reading_date=date(2024, 1, 1), summer_value=500, winter_value=50
        )
        self.assertEqual(reading.get_quota_usage_percentage(), 100)


class MultiYearQuotaTestCase(TestCase):
    """Test cases verifying the yearly summer quota resets across calendar years"""

    def setUp(self):
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 300
        self.config.save()
        MeterReading.objects.all().delete()

    def test_cumulative_usage_resets_for_new_calendar_year(self):
        """Usage accumulated near the end of one year must not carry over into the next."""
        MeterReading.objects.create(
            reading_date=date(2024, 12, 1), summer_value=290, winter_value=100
        )
        reading_2025 = MeterReading.objects.create(
            reading_date=date(2025, 1, 15), summer_value=340, winter_value=150
        )

        self.assertEqual(reading_2025.summer_usage, 50)
        # Cumulative usage for 2025 only counts 2025 readings, so it's 50, not 340
        self.assertEqual(reading_2025.get_yearly_cumulative_summer_usage(), 50)

        # 50 <= threshold (300), so the entire delta is charged at the low price
        expected_summer_cost = Decimal(50) * Decimal('36.00')
        expected_winter_cost = Decimal(50) * Decimal('40.00')
        self.assertEqual(reading_2025.total_cost, expected_summer_cost + expected_winter_cost)


class MathFiltersTestCase(TestCase):
    """Test cases for the custom template arithmetic filters"""

    def test_mul(self):
        self.assertEqual(mul(3, 4), 12.0)
        self.assertEqual(mul('2.5', '2'), 5.0)

    def test_mul_returns_zero_on_invalid_input(self):
        self.assertEqual(mul('abc', 2), 0)
        self.assertEqual(mul(None, 2), 0)

    def test_sub(self):
        self.assertEqual(sub(10, 4), 6.0)

    def test_sub_returns_zero_on_invalid_input(self):
        self.assertEqual(sub('abc', 2), 0)

    def test_div(self):
        self.assertEqual(div(10, 4), 2.5)

    def test_div_by_zero_returns_zero(self):
        self.assertEqual(div(10, 0), 0)

    def test_div_returns_zero_on_invalid_input(self):
        self.assertEqual(div('abc', 2), 0)


class MeterReadingFormTestCase(TestCase):
    """Test cases for MeterReadingForm validation"""

    def setUp(self):
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 2500
        self.config.save()
        MeterReading.objects.all().delete()

    def test_valid_form_saves_reading(self):
        form = MeterReadingForm(data={
            'reading_date': date(2024, 1, 1),
            'summer_value': 100,
            'winter_value': 50,
        })
        self.assertTrue(form.is_valid())
        reading = form.save()
        self.assertEqual(reading.summer_usage, 100)

    def test_duplicate_date_is_rejected(self):
        MeterReading.objects.create(reading_date=date(2024, 1, 1), summer_value=100, winter_value=50)

        form = MeterReadingForm(data={
            'reading_date': date(2024, 1, 1),
            'summer_value': 200,
            'winter_value': 100,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('already exists', str(form.errors))

    def test_negative_consumption_is_rejected(self):
        MeterReading.objects.create(reading_date=date(2024, 1, 1), summer_value=100, winter_value=50)

        form = MeterReadingForm(data={
            'reading_date': date(2024, 2, 1),
            'summer_value': 50,
            'winter_value': 60,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('negative consumption', str(form.errors))

    def test_negative_value_is_rejected(self):
        form = MeterReadingForm(data={
            'reading_date': date(2024, 1, 1),
            'summer_value': -10,
            'winter_value': 50,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('cannot be negative', str(form.errors))


class DashboardViewTestCase(TestCase):
    """Test cases for the dashboard view's context data and pagination"""

    def setUp(self):
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 2500
        self.config.save()
        MeterReading.objects.all().delete()

    def test_dashboard_with_no_readings(self):
        response = self.client.get(reverse('energy_tracker:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['year_stats']['summer_usage'], 0)
        self.assertEqual(response.context['year_stats']['quota_remaining'], self.config.summer_threshold)
        self.assertNotIn('latest_reading', response.context)

    def test_dashboard_shows_current_year_statistics(self):
        current_year = timezone.now().year
        reading = MeterReading.objects.create(
            reading_date=date(current_year, 6, 1), summer_value=100, winter_value=50
        )

        response = self.client.get(reverse('energy_tracker:dashboard'))

        self.assertEqual(response.context['year_stats']['summer_usage'], 100)
        self.assertEqual(response.context['year_stats']['winter_usage'], 50)
        self.assertEqual(response.context['latest_reading'], reading)
        self.assertEqual(response.context['current_summer_value'], 100)

    def test_dashboard_year_statistics_exclude_other_years(self):
        current_year = timezone.now().year
        MeterReading.objects.create(
            reading_date=date(current_year - 1, 6, 1), summer_value=500, winter_value=200
        )

        response = self.client.get(reverse('energy_tracker:dashboard'))

        self.assertEqual(response.context['year_stats']['summer_usage'], 0)
        self.assertNotIn('latest_reading', response.context)

    def test_dashboard_paginates_readings_by_ten(self):
        for i in range(15):
            MeterReading.objects.create(
                reading_date=date(2024, 1, 1) + timedelta(days=i),
                summer_value=100 + i,
                winter_value=50 + i,
            )

        first_page = self.client.get(reverse('energy_tracker:dashboard'))
        self.assertEqual(len(first_page.context['recent_readings']), 10)
        self.assertTrue(first_page.context['is_paginated'])

        second_page = self.client.get(reverse('energy_tracker:dashboard'), {'page': 2})
        self.assertEqual(len(second_page.context['recent_readings']), 5)


class MeterReadingCreateViewTestCase(TestCase):
    """Test cases for the class-based meter reading creation view"""

    def setUp(self):
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 2500
        self.config.save()
        MeterReading.objects.all().delete()

    def test_get_renders_form(self):
        response = self.client.get(reverse('energy_tracker:add_reading'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add New Meter Reading')

    def test_post_valid_data_creates_reading_and_redirects(self):
        response = self.client.post(reverse('energy_tracker:add_reading'), data={
            'reading_date': '2024-01-01',
            'summer_value': 100,
            'winter_value': 50,
        })

        self.assertRedirects(response, reverse('energy_tracker:dashboard'))
        self.assertEqual(MeterReading.objects.count(), 1)
        reading = MeterReading.objects.get()
        self.assertEqual(reading.summer_usage, 100)

    def test_post_invalid_data_does_not_create_reading(self):
        response = self.client.post(reverse('energy_tracker:add_reading'), data={
            'reading_date': '2024-01-01',
            'summer_value': -5,
            'winter_value': 50,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(MeterReading.objects.count(), 0)


class FunctionBasedAddReadingViewTestCase(TestCase):
    """Test cases for the function-based add_reading view"""

    def setUp(self):
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 2500
        self.config.save()
        MeterReading.objects.all().delete()

    def test_get_prefills_form_from_previous_reading(self):
        previous = MeterReading.objects.create(
            reading_date=date(2024, 1, 1), summer_value=100, winter_value=50
        )

        response = self.client.get(reverse('energy_tracker:add_reading_func'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['previous_reading'], previous)
        self.assertEqual(response.context['form'].initial['summer_value'], 100)
        self.assertEqual(response.context['form'].initial['winter_value'], 50)

    def test_post_valid_data_creates_reading_and_redirects(self):
        response = self.client.post(reverse('energy_tracker:add_reading_func'), data={
            'reading_date': '2024-01-01',
            'summer_value': 100,
            'winter_value': 50,
        })

        self.assertRedirects(response, reverse('energy_tracker:dashboard'))
        self.assertEqual(MeterReading.objects.count(), 1)


class MeterReadingDetailViewTestCase(TestCase):
    """Test cases for the meter reading detail view's prev/next navigation"""

    def setUp(self):
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 2500
        self.config.save()
        MeterReading.objects.all().delete()

    def test_detail_view_exposes_previous_and_next_readings(self):
        reading_a = MeterReading.objects.create(reading_date=date(2024, 1, 1), summer_value=100, winter_value=50)
        reading_b = MeterReading.objects.create(reading_date=date(2024, 2, 1), summer_value=200, winter_value=100)
        reading_c = MeterReading.objects.create(reading_date=date(2024, 3, 1), summer_value=300, winter_value=150)

        response = self.client.get(reverse('energy_tracker:reading_detail', args=[reading_b.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['previous_reading'], reading_a)
        self.assertEqual(response.context['next_reading'], reading_c)

    def test_first_reading_has_no_previous_reading(self):
        reading_a = MeterReading.objects.create(reading_date=date(2024, 1, 1), summer_value=100, winter_value=50)
        MeterReading.objects.create(reading_date=date(2024, 2, 1), summer_value=200, winter_value=100)

        response = self.client.get(reverse('energy_tracker:reading_detail', args=[reading_a.pk]))

        self.assertIsNone(response.context['previous_reading'])
        self.assertIsNotNone(response.context['next_reading'])

    def test_missing_reading_returns_404(self):
        response = self.client.get(reverse('energy_tracker:reading_detail', args=[9999]))
        self.assertEqual(response.status_code, 404)


class MeterReadingAdminDisplayTestCase(TestCase):
    """Test cases for MeterReadingAdmin's custom display methods"""

    def setUp(self):
        self.config = TariffConfig.get_config()
        self.config.winter_price = Decimal('40.00')
        self.config.summer_price_low = Decimal('36.00')
        self.config.summer_price_high = Decimal('70.00')
        self.config.summer_threshold = 300
        self.config.save()
        MeterReading.objects.all().delete()
        self.admin = MeterReadingAdmin(MeterReading, AdminSite())

    def test_cost_breakdown_for_saved_reading(self):
        reading = MeterReading.objects.create(reading_date=date(2024, 1, 1), summer_value=100, winter_value=50)

        html = self.admin.cost_breakdown(reading)

        self.assertIn(f"Winter: {reading.winter_usage} kWh", html)
        self.assertIn(f"{reading.total_cost:.2f} Ft", html)

    def test_cost_breakdown_for_unsaved_reading(self):
        reading = MeterReading(reading_date=date(2024, 1, 1), summer_value=100, winter_value=50)
        self.assertEqual(self.admin.cost_breakdown(reading), "Save reading to calculate costs")

    def test_quota_status_uses_green_below_seventy_percent(self):
        reading = MeterReading.objects.create(reading_date=date(2024, 1, 1), summer_value=100, winter_value=50)
        self.assertIn('green', self.admin.quota_status(reading))

    def test_quota_indicator_symbols_reflect_usage_level(self):
        low_reading = MeterReading.objects.create(reading_date=date(2024, 1, 1), summer_value=100, winter_value=50)
        self.assertIn('✓', self.admin.quota_indicator(low_reading))
        self.assertIn('green', self.admin.quota_indicator(low_reading))

        # Cumulative usage (100 + 180 = 280) is at 93.3% of the 300 kWh threshold -> red/✗
        high_reading = MeterReading.objects.create(reading_date=date(2024, 2, 1), summer_value=280, winter_value=60)
        self.assertIn('✗', self.admin.quota_indicator(high_reading))
        self.assertIn('red', self.admin.quota_indicator(high_reading))

    def test_quota_indicator_for_unsaved_reading(self):
        reading = MeterReading(reading_date=date(2024, 1, 1), summer_value=100, winter_value=50)
        self.assertEqual(self.admin.quota_indicator(reading), "—")


class TariffConfigAdminPermissionsTestCase(TestCase):
    """Test cases for TariffConfigAdmin's singleton enforcement"""

    def setUp(self):
        self.admin = TariffConfigAdmin(TariffConfig, AdminSite())

    def test_cannot_add_when_a_config_already_exists(self):
        TariffConfig.get_config()
        self.assertFalse(self.admin.has_add_permission(request=None))

    def test_can_add_when_no_config_exists_yet(self):
        TariffConfig.objects.all().delete()
        self.assertTrue(self.admin.has_add_permission(request=None))

    def test_cannot_delete_the_singleton(self):
        config = TariffConfig.get_config()
        self.assertFalse(self.admin.has_delete_permission(request=None, obj=config))
