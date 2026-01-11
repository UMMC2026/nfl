#!/usr/bin/env python3
"""
Test domain validator on tonight's slate
"""

from ufa.analysis.domain_validator import batch_classify, print_validation_report

# Test on tonight's key picks
picks = [
    {
        'player': 'Keyonte George',
        'stat': 'points O 25.5',
        'line': 25.5,
        'mu': 26.5,
        'sigma': 2.1,
        'confidence': 75.0,
    },
    {
        'player': 'Lauri Markkanen',
        'stat': 'points O 26.5',
        'line': 26.5,
        'mu': 27.5,
        'sigma': 3.2,
        'confidence': 72.0,
    },
    {
        'player': 'Jaden Ivey',
        'stat': 'points O 10.5',
        'line': 10.5,
        'mu': 15.6,
        'sigma': 4.1,
        'confidence': 55.0,
    },
    {
        'player': 'Kevin Durant',
        'stat': 'pts+reb+ast O 37.5',
        'line': 37.5,
        'mu': 988.3,
        'sigma': None,
        'confidence': 62.0,
    },
    {
        'player': 'Jalen Duren',
        'stat': 'rebounds O 10.5',
        'line': 10.5,
        'mu': None,
        'sigma': None,
        'confidence': 65.0,
    },
    {
        'player': 'Terance Mann',
        'stat': 'points O 6.5',
        'line': 6.5,
        'mu': 9.7,
        'sigma': 5.7,
        'confidence': 50.0,
    },
    {
        'player': 'PJ Washington',
        'stat': 'points O 12.5',
        'line': 12.5,
        'mu': 17.9,
        'sigma': 7.0,
        'confidence': 52.0,
    },
    {
        'player': 'Alperen Sengun',
        'stat': 'points O 20.5',
        'line': 20.5,
        'mu': 1034.6,
        'sigma': 381.4,
        'confidence': 65.0,
    },
    {
        'player': 'Bam Adebayo',
        'stat': 'pts+reb+ast O 27.5',
        'line': 27.5,
        'mu': None,
        'sigma': None,
        'confidence': 65.0,
    },
]

results = batch_classify(picks)
print_validation_report(results)
