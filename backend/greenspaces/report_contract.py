"""Pure validation/formatting for report configuration and frozen snapshots."""
from uuid import UUID

REPORT_TYPE = 'Accessibility planning report'
SECTIONS = ('executive_summary', 'coverage_indicators', 'priority_gap', 'inventory', 'methodology')


def parse_report(payload):
    if not isinstance(payload, dict) or set(payload) != {'report_type', 'area', 'reporting_period', 'sections', 'request_key'}:
        raise ValueError('Send report_type, area, reporting_period, sections and request_key only.')
    if payload['report_type'] != REPORT_TYPE:
        raise ValueError('Select Accessibility planning report.')
    area = payload['area']
    if area is not None and (type(area) is not int or not 0 < area <= 2147483647):
        raise ValueError('Select an available administrative area.')
    period = payload['reporting_period']
    if not isinstance(period, str) or not 1 <= len(period.strip()) <= 100 or any(ord(c) < 32 for c in period):
        raise ValueError('Reporting period must be 1–100 printable characters.')
    sections = payload['sections']
    if not isinstance(sections, list) or not sections or not all(isinstance(s, str) and s in SECTIONS for s in sections) or len(set(sections)) != len(sections):
        raise ValueError('Choose at least one valid section, without duplicates.')
    try:
        if not isinstance(payload['request_key'], str):
            raise ValueError()
        key = UUID(payload['request_key'])
        if key.version != 4:
            raise ValueError()
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError('A valid request key is required.') from exc
    return {'report_type': REPORT_TYPE, 'area': area, 'reporting_period': period.strip(),
            'sections': [s for s in SECTIONS if s in sections]}, key


def build_snapshot(data, config, generated_at, inventory):
    """Input comes from validated database queries, not the browser."""
    area_name = next((a['area_name'] for a in data['options']['areas'] if a['area_id'] == config['area']), 'Petaling District')
    return {'version': 1, 'title': 'Accessibility Coverage Report', 'area_name': area_name,
            'report_type': config['report_type'], 'reporting_period': config['reporting_period'],
            'generated_at': generated_at, 'sections': config['sections'], 'radius_m': 1000,
            'coverage_basis': data['coverage_basis'], 'summary': data['summary'],
            'areas': data['areas'], 'categories': data['categories'],
            'inventory': inventory[:1000], 'inventory_limited': len(inventory) > 1000,
            'limitations': [
                'Coverage is land within 1 km of uploaded parks, not population coverage or walking routes.',
                'Population gaps, priority rankings, high/medium/low accessibility classes and baseline changes are not assessed.',
                'The reporting period is a label, not a historical data filter. Figures are a snapshot at generation time.',
                'Mapped polygon area excludes point-only footprints. Overlapping administrative areas are not additive.',
            ]}
