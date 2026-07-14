Datasets used by the manuscript experiments
-------------------------------------------
focos_ce_INPE_2024_2026.csv   INPE BDQueimadas hotspots, Ceara, 2024-2026 (main validation)
climate_ceara_90d.json        Open-Meteo daily climate, 15 municipalities, 90+ days
firms_ceara_7d.json           NASA FIRMS active fires snapshot (7 days)
inpe_ceara_historico.json     INPE historical hotspot archive (JSON)
focos_ma_dry_2025.csv         INPE hotspots, Maranhao dry season 2025 (external-state validation)
focos_pi_dry_2025.csv         INPE hotspots, Piaui dry season 2025 (external-state validation)

Brazil-wide raw monthly INPE files (focos_mensal_br_YYYYMM.csv, ~580 MB) are
not bundled; regenerate them with scripts/reproduce_inpe_data.sh, which
downloads directly from the INPE open data portal.
