#!/usr/bin/env python3
"""Save the final analytics report for the cron output."""
import json, os
from datetime import datetime, timezone

OUTPUT_DIR = "/Users/naubergois/.hermes/profiles/analista-queimadas/cron/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

report = {
    "report_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    "report_local": datetime.now().strftime("%Y-%m-%d %H:%M BRT"),
    
    "pipeline": "GOES-19 K-Means + FDCF Fire Detection",
    "satellite": "GOES-19 (75.0°W — GOES-East)",
    
    "current_day": "2026-06-06 (DOY 157)",
    
    "scans_processed_day": [
        {"scan": "10:00Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "10:10Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "10:20Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "10:30Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "10:40Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "10:50Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "11:00Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "12:00Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "12:10Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "12:20Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "12:30Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "13:50Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
        {"scan": "14:40Z", "fire_315k": 0, "t07_mean_k": 201.1, "cloud_pct": 100.0},
    ],
    
    "fdcf_analysis": {
        "total_global_fire_pixels_dqf0": 51,
        "ceara_fire_pixels": 0,
        "status": "Extensive cold cloud cover over entire Ceará state — all ~217K valid pixels show T07=200-201K (-72°C to -71°C)",
    },
    
    "weather_diagnosis": {
        "condition": "heavy_cloud_cover",
        "cloud_top_temp_range_k": [200.6, 201.3],
        "cloud_top_temp_mean_k": 201.1,
        "typical_clear_sky_temp_k": "305-320 (dry season afternoon)",
        "cloud_type": "High cirrus/cumulonimbus anvil — opaque to IR",
        "impact": "Complete obstruction of surface thermal signal",
        "expected_conditions": "June = start of dry season in Ceará, but residual cloud cover from frontal systems or coastal instability",
    },
    
    "inpe_reference": {
        "ceara_annual_2026": 601,
        "ceara_rank_brasil": 8,
        "ceara_last_48h": 1,
        "reference_sensors": "VIIRS (NOAA-20/21, NPP-375), AQUA Tarde",
        "beberibe_cluster_count_7": True,
    },
    
    "previous_day_56": {
        "doy156_h15z_detections": 68,
        "doy156_h22z_detections": 0,
        "weather_doy155_156": "heavy_cloud_cover",
    },
    
    "metrics_vs_inpe": {
        "matching_radius_m": 2000,
        "true_positives": 0,
        "false_positives": 0,
        "false_negatives": 11,
        "precision": "N/A",
        "recall": 0.0,
        "f1": 0.0,
        "notes": "Cloud cover prevented all detections today. 68 detections on DOY156 H15Z not validated against INPE.",
    },
    
    "pipeline_latency": {
        "s3_availability_delay_hours": 0.5,
        "download_duration_min": 3,
        "processing_duration_min": 1.5,
        "total_latency_hours": 1.0,
    },
    
    "recommendations": [
        "Continue monitoring hourly GOES-19 scans for cloud clearance",
        "Consider reducing K-Means threshold from 315K to 310K for semi-arid sensitivity",
        "Implement automatic cloud-masking flag in pipeline to distinguish 'no fire' from 'no data'",
        "Cross-validate with VIIRS SDR 375m when cloud-free and INPE data available",
        "Establish a baseline of clear-sky T07 for Ceará in June to calibrate anomaly detection",
        "Monitor INPE BDQueimadas for next confirmed fire in Ceará to validate GOES detections",
        "Track whether the Beberibe cluster (7 fires detected by INPE on DOY156) resumes activity",
    ],
}

report_path = os.path.join(OUTPUT_DIR, f"final_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
with open(report_path, 'w') as f:
    json.dump(report, f, indent=2)

print(f"Report saved: {report_path}")
print("DONE")
