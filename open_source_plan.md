# Open-Source Release Plan: FLIR Thermal Analyzer

## Repository Analysis Summary

**What this project is:** A Flask-based web application for processing FLIR thermal camera images. It aligns RGB and thermal images, performs ROI-based analysis with AI-powered background removal (rembg/BiRefNet), samples temperature data using Farthest Point Sampling, and stores results in SQLite. Supports Docker and native Python deployment.

**Tech stack:** Python 3.10+, Flask, OpenCV, NumPy, rembg (ONNX), scikit-image, Gunicorn/Waitress, SQLite, Docker

**Current state:**
- No `.gitignore` — `venv/`, `__pycache__/`, `.DS_Store`, `flir_data.db`, and uploaded/processed images would be committed
- No `LICENSE` file
- Two informal README drafts (`README_0.md` in Chinese, `README2.md` is an AI chat log, not a README)
- No community health files (CONTRIBUTING, CODE_OF_CONDUCT, SECURITY)
- No CI/CD workflows
- No git repository initialized yet

---

## Files to Create/Update

| File | Rationale |
|------|-----------|
| `.gitignore` | **Critical.** Prevents committing `venv/`, `__pycache__/`, `.DS_Store`, `*.db`, uploaded/processed images, model weights |
| `README.md` | **Critical.** Professional English README with project overview, screenshots placeholder, features, prerequisites, installation (Docker + native), API reference, architecture overview. Incorporates content from `README_0.md` |
| `LICENSE` | **Critical.** MIT license as requested |
| `CONTRIBUTING.md` | Standard contributing guide with setup instructions, code style, PR process |
| `CODE_OF_CONDUCT.md` | Contributor Covenant v2.1 (industry standard) |
| `SECURITY.md` | Security policy with responsible disclosure process |
| `CHANGELOG.md` | Initial changelog entry for v1.0.0 |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Structured bug report template (YAML form) |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Structured feature request template (YAML form) |
| `.github/ISSUE_TEMPLATE/config.yml` | Issue template chooser config |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR template with checklist |
| `.github/workflows/ci.yml` | CI: lint, test skeleton, Docker build verification |
| `.github/workflows/release.yml` | Release: triggered on tags, creates GitHub Release with Docker image |

## Files NOT Created (and why)

- **No test files** — no tests exist; I won't invent a test suite
- **No `setup.py` / `pyproject.toml`** — this is a web app deployed via Docker, not a library
- **No `.env.example`** — the app uses env vars only inside Docker (already defined in Dockerfile/compose)
- **No Dependabot config** — optional, not requested

## Files NOT Modified

- All application source code (`app.py`, `database.py`, `image_processing.py`, `index.html`, `style.css`) — **no logic changes**
- `Dockerfile`, `docker-compose.yml`, `run_server.sh`, `run_server.bat` — working as-is
- `README_0.md`, `README2.md` — preserved as historical reference
