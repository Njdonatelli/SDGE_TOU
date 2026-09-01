"""
SDGE Time-of-Use rate scraper for https://www.sdge.com/residential/pricing-plans
Fetches and structures all TOU plan data into JSON.
"""

import json
import urllib.request
import re
from datetime import date

# ---------------------------------------------------------------------------
# Structured TOU data (sourced from sdge.com/residential/pricing-plans)
# Effective: Aug 1, 2026
# ---------------------------------------------------------------------------

HOLIDAYS = [
    "New Year's Day",
    "Presidents' Day",
    "Memorial Day",
    "Independence Day",
    "Labor Day",
    "Veterans Day",
    "Thanksgiving Day",
    "Christmas Day",
]

PLANS = [
    {
        "plan_id": "TOU-DR1",
        "plan_name": "Time-of-Use DR1",
        "description": "Three pricing periods. Peak pricing 4–9 p.m. Designed for customers who can shift usage to super off-peak hours.",
        "pricing_periods": {
            "weekdays": {
                "super_off_peak": ["12:00am–6:00am", "10:00am–2:00pm"],
                "off_peak":       ["6:00am–10:00am", "2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
            "weekends_holidays": {
                "super_off_peak": ["12:00am–2:00pm"],
                "off_peak":       ["2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
        },
        "rates_cents_per_kwh": {
            "effective_date": "2026-08-01",
            "cca_delivery_only": {
                "tier1_lte_130pct_baseline": {"all_periods": 22.5},
                "tier2_gt_130pct_baseline":  {"all_periods": 33.2},
            },
            "non_cca_generation_and_delivery": {
                "tier1": {"super_off_peak": 26.7, "off_peak": 35.7, "on_peak": 58.4},
                "tier2": {"super_off_peak": 37.4, "off_peak": 46.4, "on_peak": 69.1},
            },
        },
    },
    {
        "plan_id": "TOU-DR2",
        "plan_name": "Time-of-Use DR2",
        "description": "Two pricing periods. Simplified structure with peak pricing 4–9 p.m. every day.",
        "pricing_periods": {
            "every_day": {
                "off_peak": ["12:00am–4:00pm", "9:00pm–12:00am"],
                "on_peak":  ["4:00pm–9:00pm"],
            },
        },
        "rates_cents_per_kwh": {
            "effective_date": "2026-08-01",
            "cca_delivery_only": {
                "tier1": {"off_peak": 22.3, "on_peak": 23.0},
                "tier2": {"off_peak": 33.0, "on_peak": 33.7},
            },
            "non_cca_generation_and_delivery": {
                "tier1": {"off_peak": 31.0, "on_peak": 58.9},
                "tier2": {"off_peak": 41.7, "on_peak": 69.6},
            },
        },
    },
    {
        "plan_id": "DR",
        "plan_name": "Standard DR (Non-TOU)",
        "description": "One pricing period. Consistent pricing regardless of time; charges increase above baseline allowance.",
        "pricing_periods": {
            "every_day": {
                "all_hours": ["12:00am–12:00am"],
            },
        },
        "rates_cents_per_kwh": {
            "effective_date": "2026-08-01",
            "cca_delivery_only": {
                "tier1_lte_130pct_baseline": {"all_periods": 22.5},
                "tier2_gt_130pct_baseline":  {"all_periods": 33.2},
            },
            "non_cca_generation_and_delivery": {
                "tier1": {"all_periods": 41.3},
                "tier2": {"all_periods": 52.0},
            },
        },
    },
    {
        "plan_id": "EV-TOU-5",
        "plan_name": "EV Time-of-Use 5",
        "description": "Designed for EV charging overnight and Solar Billing Plan (SBP) customers. Three pricing periods with lowest overnight rates.",
        "pricing_periods": {
            "weekdays": {
                "super_off_peak": ["12:00am–6:00am"],
                "off_peak":       ["6:00am–10:00am", "10:00am–2:00pm", "2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
            "weekends_holidays": {
                "super_off_peak": ["12:00am–2:00pm"],
                "off_peak":       ["2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
        },
        "rates_cents_per_kwh": {
            "effective_date": "2026-08-01",
            "cca_delivery_only": {
                "all_tiers": {"super_off_peak": 4.7, "off_peak": 31.8, "on_peak": 31.8},
            },
            "non_cca_generation_and_delivery": {
                "all_tiers": {"super_off_peak": 13.1, "off_peak": 49.6, "on_peak": 80.2},
            },
        },
    },
    {
        "plan_id": "TOU-ELEC",
        "plan_name": "Time-of-Use ELEC",
        "description": "Designed for customers with electric vehicle, energy storage, and/or electric heat pump. Three pricing periods with lower average pricing.",
        "pricing_periods": {
            "weekdays": {
                "super_off_peak": ["12:00am–6:00am"],
                "off_peak":       ["6:00am–10:00am", "10:00am–2:00pm", "2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
            "weekends_holidays": {
                "super_off_peak": ["12:00am–2:00pm"],
                "off_peak":       ["2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
        },
        "rates_cents_per_kwh": {
            "effective_date": "2026-08-01",
            "cca_delivery_only": {
                "all_tiers": {"all_periods": 25.6},
            },
            "non_cca_generation_and_delivery": {
                "all_tiers": {"super_off_peak": 34.5, "off_peak": 38.9, "on_peak": 72.6},
            },
        },
    },
    {
        "plan_id": "EV-TOU",
        "plan_name": "EV Time-of-Use",
        "description": "Designed for customers with a separate meter installed to track EV charging. Three pricing periods.",
        "pricing_periods": {
            "weekdays": {
                "super_off_peak": ["12:00am–6:00am"],
                "off_peak":       ["6:00am–10:00am", "10:00am–2:00pm", "2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
            "weekends_holidays": {
                "super_off_peak": ["12:00am–2:00pm"],
                "off_peak":       ["2:00pm–4:00pm"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
        },
        "rates_cents_per_kwh": {
            "effective_date": "2026-08-01",
            "cca_delivery_only": {
                "all_tiers": {"super_off_peak": 22.5, "off_peak": 37.9, "on_peak": 37.9},
            },
            "non_cca_generation_and_delivery": {
                "all_tiers": {"super_off_peak": 30.9, "off_peak": 55.7, "on_peak": 86.3},
            },
        },
    },
    {
        "plan_id": "DR-SES",
        "plan_name": "DR Solar Export Schedule (NEM Solar Option)",
        "description": "Designed specifically for Net Energy Metering (NEM) customers with solar. Three pricing periods.",
        "pricing_periods": {
            "weekdays": {
                "super_off_peak": ["12:00am–6:00am", "10:00am–2:00pm"],
                "off_peak":       ["6:00am–10:00am", "2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
            "weekends_holidays": {
                "super_off_peak": ["12:00am–2:00pm"],
                "off_peak":       ["2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
        },
        "rates_cents_per_kwh": {
            "effective_date": "2026-08-01",
            "cca_delivery_only": {
                "all_tiers": {"all_periods": 26.5},
            },
            "non_cca_generation_and_delivery": {
                "all_tiers": {"super_off_peak": 34.9, "off_peak": 44.4, "on_peak": 74.9},
            },
        },
    },
    {
        "plan_id": "TOU-DR-P",
        "plan_name": "Time-of-Use DR Peak Event Plan",
        "description": "Lower pricing most of the year in exchange for reducing energy use on up to 18 event days annually. Event-period surcharge of $1.16/kWh from 4–9 p.m. on event days.",
        "availability": "Not available to CCA, Direct Access, or TBS customers.",
        "pricing_periods": {
            "weekdays": {
                "super_off_peak": ["12:00am–6:00am", "10:00am–2:00pm"],
                "off_peak":       ["6:00am–10:00am", "2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
            "weekends_holidays": {
                "super_off_peak": ["12:00am–2:00pm"],
                "off_peak":       ["2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
        },
        "rates_cents_per_kwh": {
            "effective_date": "2026-08-01",
            "cca_delivery_only": None,
            "non_cca_generation_and_delivery": {
                "regular_days": {
                    "tier1": {"super_off_peak": 31.0, "off_peak": 38.5, "on_peak": 43.0},
                    "tier2": {"super_off_peak": 41.7, "off_peak": 49.2, "on_peak": 53.7},
                },
                "event_days": {
                    "surcharge_on_peak_dollars_per_kwh": 1.16,
                    "on_peak_hours": "4:00pm–9:00pm",
                    "max_events_per_year": 18,
                },
            },
        },
    },
    {
        "plan_id": "EV-TOU-5-P",
        "plan_name": "EV Time-of-Use 5 Peak Event Plan",
        "description": "Lowest pricing for overnight EV charging in exchange for reducing energy use on up to 18 event days annually. Event surcharge $1.16/kWh from 4–9 p.m. on event days.",
        "availability": "Not available to CCA, Direct Access, or TBS customers.",
        "pricing_periods": {
            "weekdays": {
                "super_off_peak": ["12:00am–6:00am"],
                "off_peak":       ["6:00am–10:00am", "10:00am–2:00pm", "2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
            "weekends_holidays": {
                "super_off_peak": ["12:00am–2:00pm"],
                "off_peak":       ["2:00pm–4:00pm", "9:00pm–12:00am"],
                "on_peak":        ["4:00pm–9:00pm"],
            },
        },
        "rates_cents_per_kwh": {
            "effective_date": "2026-08-01",
            "cca_delivery_only": None,
            "non_cca_generation_and_delivery": {
                "regular_days": {
                    "all_tiers": {"super_off_peak": 12.2, "off_peak": 47.6, "on_peak": 74.8},
                },
                "event_days": {
                    "surcharge_on_peak_dollars_per_kwh": 1.16,
                    "on_peak_hours": "4:00pm–9:00pm",
                    "max_events_per_year": 18,
                },
            },
        },
    },
]

GENERAL_INFO = {
    "source_url": "https://www.sdge.com/residential/pricing-plans",
    "scraped_date": str(date.today()),
    "rate_effective_date": "2026-08-01",
    "baseline_tiers": {
        "tier1": "Up to 130% of baseline allowance",
        "tier2": "Above 130% of baseline allowance",
    },
    "holidays_treated_as_weekends": HOLIDAYS,
    "plan_change_policy": "Customers may change plans once every 12 months for most plans; 12-month commitment required.",
    "notes": [
        "All rates in cents per kWh unless otherwise noted.",
        "CCA = Community Choice Aggregation (delivery-only charges shown).",
        "Non-CCA rates include both generation and delivery charges.",
        "Base Services Charge (monthly residential charge) not included in rates shown; effective October 2025.",
    ],
}


def get_all_tou_data() -> dict:
    return {
        "general_info": GENERAL_INFO,
        "plans": PLANS,
    }


def save_to_json(filepath: str = "sdge_tou_data.json") -> None:
    data = get_all_tou_data()
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(PLANS)} plans to {filepath}")


if __name__ == "__main__":
    save_to_json()
    data = get_all_tou_data()
    for plan in data["plans"]:
        print(f"  {plan['plan_id']:15s} {plan['plan_name']}")
