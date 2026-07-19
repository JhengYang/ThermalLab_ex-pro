# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-19

### Added
- Initial open-source release of FLIR Thermal Analyzer.
- Flask-based web application for image alignment and processing.
- Integration with `rembg` (BiRefNet) for AI-powered background removal.
- Farthest Point Sampling (FPS) algorithm for temperature mapping.
- SQLite integration for saving experimental data and results.
- Export functionality for CSV and JSON.
- Docker and `docker-compose` setup for easy deployment.
- Concurrent request handling via Gunicorn and Waitress.
- `run_server.sh` and `run_server.bat` scripts for local setup.
