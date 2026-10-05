.PHONY: site-data site site-dev site-check

# Regenerate the website dataset from opennav_benchmark_logs/.
site-data:
	cd opennav_benchmark_analysis && python3 export_site_data.py

# What CI's `data` job runs: the log tree must match the CATEGORIES registry,
# and the committed dataset must match a fresh export.
site-check:
	cd opennav_benchmark_analysis && python3 export_site_data.py --strict
	git diff --exit-code site/src/data site/public/data

# Build the static website into site/dist/.
site: site-data
	cd site && npm ci && npm run build

# Serve the website locally with hot reload.
site-dev:
	cd site && npm run dev
