# H-Tariff Energy Tracker

A Django web application for tracking dual-register electricity meter readings with tiered pricing calculations. Designed for Hungarian H-tariff energy billing systems with separate summer and winter registers and quota-based pricing.

## 🌟 Features

- **Dual Register Tracking**: Monitor both summer and winter electricity meter readings
- **Tiered Pricing**: Automatic calculation of costs based on quota thresholds
- **Price Snapshotting**: Historical records preserve pricing at time of reading
- **Comprehensive Validation**: Prevents data entry errors and negative consumption
- **Admin Interface**: Full Django admin integration with detailed cost breakdowns
- **Responsive Design**: Modern Bootstrap-based UI with progress indicators
- **Test Coverage**: Comprehensive test suite ensuring reliability

## 🏗️ Architecture

### System Overview

The H-Tariff Tracker implements a sophisticated energy monitoring system that handles:
- **Meter Reading Management**: Input and storage of electricity meter data
- **Cost Calculation**: Real-time computation of energy costs using tiered pricing
- **Historical Data Integrity**: Immutable pricing snapshots for accurate historical records
- **User Validation**: Comprehensive input validation to prevent data corruption

### Data Models

#### TariffConfig
Singleton configuration model storing pricing parameters:
- Winter price per kWh
- Summer low price (below quota)
- Summer high price (above quota)  
- Yearly summer quota threshold

#### MeterReading
Core model for storing meter readings with calculated fields:
- Reading date and register values
- Calculated usage deltas
- Snapshotted pricing (immutable)
- Total cost computation

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- pip or uv package manager
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd H_tarifa_tracker
   ```

2. **Set up virtual environment**
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure database**
   ```bash
   python manage.py migrate
   ```

4. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

5. **Run development server**
   ```bash
   python manage.py runserver
   ```

6. **Access the application**
   - Main application: http://127.0.0.1:8000/
   - Admin interface: http://127.0.0.1:8000/admin/

## 📊 Usage Guide

### Adding Meter Readings

1. Navigate to the dashboard
2. Click "Add New Reading" or use `/reading/add/`
3. Enter:
   - **Reading Date**: When the meter was read
   - **Summer Value**: Current summer register reading
   - **Winter Value**: Current winter register reading
4. Click "Save Reading"

### Understanding the Display

#### Dashboard Overview
- **Recent Readings**: Paginated list of meter readings (10 per page)
- **Year Statistics**: Current year consumption and costs
- **Quota Status**: Visual progress bar showing summer quota usage

#### Cost Breakdown
Each reading displays:
- **Winter Cost**: Simple multiplication (usage × winter price)
- **Summer Cost**: Tiered calculation based on quota crossing
- **Total Cost**: Combined winter and summer costs

#### Tiered Pricing Logic
Summer pricing follows this logic:
1. **Below Quota**: All usage at low price
2. **Above Quota**: All usage at high price  
3. **Crossing Quota**: Split calculation (remaining quota at low price, excess at high price)

### Admin Interface Features

The Django admin provides advanced management:
- **Detailed Cost Breakdown**: HTML-formatted cost analysis
- **Quota Status Visualization**: Progress bars with color coding
- **Historical Pricing**: Immutable price snapshots
- **Bulk Operations**: Mass data management capabilities

## 🧪 Testing

### Running Tests

```bash
# Run all tests
python manage.py test

# Run with verbosity
python manage.py test --verbosity=2

# Run specific test cases
python manage.py test energy_tracker.tests.MeterReadingTestCase
```

### Test Coverage

The test suite includes:

#### Core Functionality Tests
- **First Reading Handling**: Verifies proper handling of initial readings
- **Consumption Calculation**: Validates usage delta computations
- **Tiered Pricing Logic**: Tests quota crossing calculations
- **Price Isolation**: Ensures historical records are protected

#### Edge Case Tests
- **Negative Consumption Prevention**: Validates input protection
- **Boundary Conditions**: Tests quota threshold scenarios
- **Data Integrity**: Ensures snapshot immutability

#### Model Tests
- **TariffConfig Validation**: Singleton behavior and price relationships
- **Form Validation**: User input sanitization

### Test-Driven Development

The project follows a test-driven approach:
1. **Analysis**: Code review to identify potential issues
2. **Reproduction**: Unit tests that demonstrate bugs
3. **Fixes**: Minimal, targeted code corrections
4. **Verification**: Tests confirm resolution
5. **Regression Testing**: Ensure no existing functionality breaks

## 🔧 Configuration

### Tariff Settings

Access tariff configuration via:
- **Admin Interface**: `/admin/energy_tracker/tariffconfig/1/change/`
- **Direct Model**: `TariffConfig.get_config()`

### Pricing Parameters

- **Winter Price**: Fixed rate for winter consumption
- **Summer Low Price**: Discounted rate below quota threshold
- **Summer High Price**: Market rate above quota threshold
- **Summer Threshold**: Yearly quota limit in kWh

### Customization

#### Adding New Pricing Rules
Modify `MeterReading._calculate_summer_cost()` method in `models.py`.

#### Custom Validation
Extend `MeterReading.clean()` and `MeterReadingForm.clean()` methods.

#### Template Customization
Templates located in `energy_tracker/templates/energy_tracker/`:
- `base.html`: Main layout and navigation
- `dashboard.html`: Overview page
- `reading_detail.html`: Individual reading view
- `reading_form.html`: Data entry form

## 🛡️ Data Integrity

### Validation Rules

#### Input Validation
- **Non-negative Values**: All meter readings must be ≥ 0
- **Chronological Order**: New readings must be ≥ previous readings
- **Date Uniqueness**: Only one reading per date allowed
- **Price Relationships**: Low price must be < high price

#### Business Logic Protection
- **Negative Consumption Prevention**: Blocks decreasing meter values
- **Immutable History**: Price changes don't affect existing records
- **Singleton Configuration**: Prevents multiple tariff configurations
- **Cascade Recalculation**: Editing a past reading automatically recalculates usage deltas and costs for all subsequent readings

### Error Handling

The application provides comprehensive error messages:
- **Form Validation**: User-friendly error messages
- **Model Validation**: Database-level protection
- **Admin Interface**: Detailed error reporting

## 📈 Performance Considerations

### Database Optimization
- **Query Optimization**: `select_related()` for related objects
- **Indexing**: Automatic Django indexes on key fields
- **Efficient Aggregations**: Database-level calculations

### Caching Strategy
- **Configuration Caching**: TariffConfig singleton pattern
- **Template Caching**: Django template caching ready
- **Static Files**: Optimized static file serving

## 🔒 Security

### Built-in Security
- **CSRF Protection**: Django's built-in CSRF protection
- **SQL Injection Prevention**: ORM-based queries
- **XSS Protection**: Template auto-escaping
- **Admin Security**: Django admin authentication

### Data Protection
- **Input Sanitization**: Comprehensive form validation
- **Access Control**: Admin interface authentication
- **Audit Trail**: Django admin logging

## 🤝 Contributing

### Development Setup

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature-name`
3. **Install dependencies**: `uv sync`
4. **Run tests**: `python manage.py test`
5. **Make changes** with accompanying tests
6. **Submit pull request**

### Code Style

- **Python**: PEP 8 compliance
- **Django**: Best practices and conventions
- **Documentation**: Comprehensive docstrings
- **Testing**: Test-driven development approach

### Commit Guidelines

- **Clear Messages**: Descriptive commit messages
- **Atomic Changes**: One logical change per commit
- **Test Coverage**: Ensure tests pass
- **Documentation**: Update relevant documentation

## 📝 Changelog

### Version 1.0.0
- Initial release with core functionality
- Dual register meter tracking
- Tiered pricing calculations
- Comprehensive validation
- Admin interface integration
- Full test coverage

### Recent Fixes
- **Template Filter Error**: Fixed custom math filters for cost calculations
- **URL Reversal Error**: Corrected namespaced URL references
- **Admin Interface**: Fixed format_html usage in admin methods
- **Negative Consumption**: Added comprehensive validation
- **Cascade Recalculation**: Editing a past reading now updates all subsequent readings automatically
- **Data Integrity**: Added unique constraint and database index on reading date
- **Pagination**: Dashboard now paginates all readings instead of showing a fixed 10
- **Quota Display**: Dashboard shows yearly quota percentage consistently across all rows
- **Admin Access**: Admin navigation link now only visible to staff users
- **Package Rename**: Project renamed from `delej` to `htariff-tracker`

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Common Issues

#### Template Errors
- **Custom Filters**: Ensure `{% load math_filters %}` in templates
- **URL Patterns**: Use namespaced URLs (`energy_tracker:name`)

#### Validation Errors
- **Negative Consumption**: Check meter value chronology
- **Date Conflicts**: Verify unique reading dates

#### Admin Issues
- **Format Errors**: Check format_html usage in admin methods
- **URL Problems**: Verify namespaced URL patterns

### Getting Help

1. **Check Documentation**: Review this README and code comments
2. **Run Tests**: `python manage.py test` to verify installation
3. **Check Issues**: Review existing GitHub issues
4. **Create Issue**: Provide detailed error information and reproduction steps

## 🗺️ Roadmap

### Planned Features
- **Data Export**: CSV/PDF export functionality
- **Advanced Analytics**: Consumption trends and predictions
- **Multi-year Support**: Cross-year quota tracking
- **API Interface**: RESTful API for external integrations
- **Mobile Responsive**: Enhanced mobile experience
- **Notification System**: Quota alerts and reminders

### Technical Improvements
- **Performance Optimization**: Database query optimization
- **Caching Layer**: Redis integration for performance
- **Background Tasks**: Async processing for large datasets
- **Testing Expansion**: Integration and end-to-end tests

---

**H-Tariff Energy Tracker** - Accurate energy monitoring for Hungarian dual-register electricity meters.
