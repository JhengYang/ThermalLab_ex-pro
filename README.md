# FLIR Thermal Analyzer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Docker Pulls](https://img.shields.io/docker/pulls/yourusername/flir-thermal-analyzer)](https://hub.docker.com/r/yourusername/flir-thermal-analyzer)
[![CI](https://github.com/yourusername/flir-thermal-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/flir-thermal-analyzer/actions)

> Open-source thermal imaging analysis toolkit for FLIR cameras with RGB-thermal alignment, AI segmentation, and temperature measurement.

## Overview

FLIR Thermal Analyzer is designed to help researchers and engineers extract, process, and analyze temperature data from FLIR thermal imaging cameras. It supports precise alignment of RGB and thermal images, AI-powered region-of-interest (ROI) background removal using `rembg` (BiRefNet), and intelligent temperature sampling utilizing Farthest Point Sampling.

Whether you're running it locally or deploying it on a server for multiple concurrent users, this tool provides a robust, easy-to-use web interface backed by SQLite and a scalable architecture (via Gunicorn/Waitress).

## Features

- **RGB & Thermal Alignment**: Seamlessly align visual RGB and thermal spectra images.
- **AI Background Removal**: Automatically segment the subject from the background within user-defined ROIs.
- **Advanced Temperature Sampling**: Uses Farthest Point Sampling (FPS) to extract representative temperature data points.
- **Data Persistence & Export**: Saves analysis results and points into an SQLite database with 1-click export to JSON or CSV.
- **Concurrent Processing**: Engineered for multi-user server environments using Gunicorn (Linux/Mac) or Waitress (Windows) with SQLite WAL mode.
- **Docker Ready**: Effortless deployment with Docker and `docker-compose`.

## Installation

You can deploy the FLIR Thermal Analyzer using Docker (recommended) or run it natively using Python.

### Prerequisites (Native only)

If you are not using Docker, you **must** install `exiftool` on your system to extract high-precision temperature data from FLIR images:
- **Ubuntu/Debian**: `sudo apt-get install exiftool`
- **macOS**: `brew install exiftool`
- **Windows**: Download from [exiftool.org](https://exiftool.org/) and add it to your system PATH.

### Method 1: Docker (Highly Recommended)

The easiest way to get started. This automatically handles system dependencies like `exiftool` and prepares persistent data volumes.

```bash
git clone https://github.com/yourusername/flir-thermal-analyzer.git
cd flir-thermal-analyzer
docker-compose up -d
```
The server will start at `http://localhost:5050`.

### Method 2: Native Python Environment

#### Linux / macOS
```bash
git clone https://github.com/yourusername/flir-thermal-analyzer.git
cd flir-thermal-analyzer
./run_server.sh
```

#### Windows
```cmd
git clone https://github.com/yourusername/flir-thermal-analyzer.git
cd flir-thermal-analyzer
run_server.bat
```
*(The scripts will automatically create a virtual environment and install dependencies).*

## Quick Start & Usage

1. Open a web browser and navigate to `http://localhost:5050` (or your server's IP address and port 5050).
2. **Upload**: Select an RGB image and its corresponding FLIR thermal image.
3. **Analyze**: Define Regions of Interest (ROI) on the image.
4. **Process**: The system will align the images, remove the background, and sample the temperatures.
5. **Export**: Use the web interface to export your data to CSV or JSON formats.

### Usage in Local Network
To allow access to other devices on your local network:
- Find your machine's IP address or `.local` hostname (e.g., `oujy-MacBook-Pro.local`).
- Ensure port `5050` is open on your firewall.
- Access via `http://<YOUR_IP>:5050` or `http://<YOUR_HOSTNAME>.local:5050`.

## Configuration

Environment variables can be customized in the `docker-compose.yml` or `Dockerfile`:
- `FLASK_APP`: `app.py`
- `FLIR_DATA_DIR`: Directory for SQLite DB (default: `/app/data`)
- `FLIR_UPLOAD_DIR`: Directory for uploaded images (default: `/app/static/uploads`)
- `FLIR_PROCESSED_DIR`: Directory for processed output (default: `/app/static/processed`)

## Project Structure

```text
flir-thermal-analyzer/
├── app/                  # Application source code
│   ├── app.py            # Main Flask application
│   ├── database.py       # SQLite database operations
│   ├── image_processing.py # Core image alignment & thermal processing
│   ├── requirements.txt  # Python dependencies
│   ├── static/           # Static assets, CSS, uploads, processed images
│   └── templates/        # HTML templates
├── Dockerfile            # Docker image configuration
├── docker-compose.yml    # Docker services configuration
├── run_server.sh         # Linux/Mac startup script
└── run_server.bat        # Windows startup script
```

## Development

Contributions to the FLIR Thermal Analyzer are welcome!
To set up for development:

1. Fork the repository.
2. Create a virtual environment: `python3 -m venv venv`
3. Activate the environment: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows).
4. Install dependencies: `pip install -r app/requirements.txt`
5. Run the development server: `flask run --host=0.0.0.0 --port=5050 --debug`

For more details, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Roadmap

- [ ] Add comprehensive Unit and Integration tests.
- [ ] Implement user authentication and private workspaces.
- [ ] Support for video stream processing.
- [ ] Expand AI segmentation models beyond `rembg`.
- [ ] Add REST API documentation (Swagger/OpenAPI).

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## FAQ

**Q: Why does the app fail to extract temperatures without Docker?**
A: You likely missing the system dependency `exiftool`. Please refer to the "Prerequisites (Native only)" section above.

**Q: Where are my files and data saved?**
A: In Docker, they are mapped to local directories (`data/`, `uploads/`, `processed/`, `models/`) in the project root to ensure they persist between container restarts.
