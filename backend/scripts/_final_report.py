#!/usr/bin/env python3
"""Generate final analytics report and save to cron output."""
import json, os
from datetime import datetime, timezone

BASE = "/Users/naubergois/QueimandasGemeosDigitais/ceara-queimadas/backend/data"
OUTPUT_DIR = "/Users/naubergois/.hermes/profiles/analista-queimadas/cron/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Summary metrics
report = {
    "report_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    "pipeline": "GOES-19 K-Means Fire Detection",
    "satellite": "GOES-19 (75.0°W — GOES-East)",
    
    "current_scan": {
        "date": "2026-06-06",
        "doy": 157,
        "latest_scan_utc": "12:30",
        "local_time": "09:30",
        "scans_processed_today": 28,
        "fire_detections": 0,
        "weather": "heavy_cloud_cover",
        "cloud_top_temp_range_k": [200.3, 201.6],
        "cloud_top_temp_mean_k": 201.0,
    },
    
    "previous_scans": {
        "doy156_h15z_detections": 68,
        "doy156_h22z_detections": 0,
        "doy155_h15_h18_detections": 0,
        "weather_doy155_156": "heavy_cloud_cover",
    },
    
    "inpe_reference": {
        "ceara_annual_2026": 601,
        "ceara_rank_brasil": 8,
        "ceara_last_48h": 1,
        "reference_fires_listed": 11,
        "beberibe_cluster_count": 7,
        "reference_sensors": "VIIRS (NOAA-20/21, NPP-375)",
    },
    
    "pipeline_latency": {
        "s3_availability_delay_hours": 0.5,
        "download_duration_min": 7,
        "processing_duration_min": 2,
        "total_latency_hours": 1.5,
    },
    
    "metrics_vs_inpe": {
        "matching_radius_m": 2000,
        "true_positives": 0,
        "false_positives": 0,
        "false_negatives": 11,
        "precision": "N/A",
        "recall": 0.0,
        "f1": 0.0,
        "notes": "Cloud cover prevented all detections. 68 detections on DOY156 H15Z not validated against INPE."
    },
    
    "diagnosis": {
        "cause": "Extensive cold cloud cover over entire Ceará state",
        "evidence": "All 262K pixels in Ceará exhibit T07=200-201K (~-72°C)",
        "typical_clear_sky_ceara_t07": "305-320K (dry season afternoon)",
        "cloud_type": "High cirrus/cumulonimbus anvil - opaque to IR",
        "impact": "Complete obstruction of surface thermal signal",
        "expected_conditions": "June = start of dry season in Ceará, but residual cloud cover from frontal systems or coastal instability"
    },
    
    "recommendations": [
        "Continue monitoring hourly GOES-19 scans for cloud clearance",
        "Reduce K-Means threshold from 315K to 310K for semi-arid sensitivity",
        "Cross-validate with VIIRS SDR 375m when available",
        "Implement automatic cloud-masking flag in pipeline",
        "Compare with FIRMS active fire data when skies clear",
        "Re-run historical validation when coincident cloud-free AND INPE fire data exists",
    ]
}

# Save
report_path = os.path.join(OUTPUT_DIR, f"final_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
with open(report_path, 'w') as f:
    json.dump(report, f, indent=2)
print(f"Final report saved: {report_path}")
