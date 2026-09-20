"""Unit tests for benchmark.config helpers."""

from benchmark import config as config_mod


def _cfg():
    return {
        "variables": {
            "surface": ["2m_temperature", "mean_sea_level_pressure"],
            "pressure": [
                {"name": "geopotential", "level": 500},
                {"name": "temperature", "level": 850},
            ],
        },
        "region": {"lat": [15.0, 55.0], "lon": [70.0, 140.0]},
    }


def test_variables_from_config():
    assert config_mod.variables_from_config(_cfg()) == [
        "2m_temperature",
        "mean_sea_level_pressure",
        "geopotential_500",
        "temperature_850",
    ]


def test_region_from_config():
    assert config_mod.region_from_config(_cfg()) == {"lat": (15.0, 55.0), "lon": (70.0, 140.0)}
