# Smart Queue & Pickup Estimator for Campus Print Shops

A two-screen web app that helps students avoid long queues at campus print shops. Students submit print jobs and track estimated pickup times; shopkeepers manage the active queue and update order status.

## Features

- Student portal: submit page count, copies, document name, and binding type.
- Shopkeeper dashboard: view all orders, queue metrics, and update order status.
- FastAPI REST API with SQLite persistence.
- FIFO pickup-time estimate based on active work ahead in the queue.
- Student status refresh every 15 seconds while the app is open.
- Docker Compose for one-command local deployment.
- GitHub Actions workflow builds both Docker images on pushes and pull requests.

## Tech stack

- Python 3.12
- FastAPI + Pydantic
- Streamlit
- SQLite
- Docker / Docker Compose
- GitHub Actions

## Run with Docker (recommended)

Install Docker Desktop or Docker Engine with the Compose plugin, then run from the project root:

```bash
docker compose up --build
```

Open:
- Student and shopkeeper app: http://localhost:8501
- API documentation (Swagger): http://localhost:8000/docs
- API health check: http://localhost:8000/health

Stop the app:

```bash
docker compose down
```

To remove the saved SQLite database as well:

```bash
docker compose down -v
```

## Run without Docker

Terminal 1 — backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Terminal 2 — frontend:

```bash
cd frontend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The frontend defaults to `http://localhost:8000` for the API. Set `API_URL` if your backend runs elsewhere.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/orders` | Create a print order |
| GET | `/orders` | List orders |
| GET | `/orders/{id}` | Get one order and current estimate |
| PATCH | `/orders/{id}/status` | Update order status |
| GET | `/queue/summary` | Active queue metrics |

Example order:

```json
{
  "student_name": "Asha",
  "document_name": "Chemistry Lab Record",
  "pages": 45,
  "binding": "spiral",
  "copies": 1
}
```

Allowed binding values: `none`, `soft`, `spiral`.

Allowed statuses: `queued`, `printing`, `binding`, `ready`, `collected`, `cancelled`.

## How the pickup estimate works

The starter estimator assumes one processing lane and FIFO order:

`estimated seconds = (pages × copies × print seconds per page) + binding time`

It adds the estimated remaining work for active orders ahead of the new order. Default assumptions in `backend/app/main.py`:

- Printing: 2 seconds per page
- No binding: 0 seconds
- Soft binding: 180 seconds
- Spiral binding: 300 seconds

These are demo assumptions, not measured shop performance. Tune them using real shop timings. The current implementation does not account for printer parallelism, staff availability, machine failures, or partially completed work.

## Project structure

```text
smart_queue_print_shop/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── .github/workflows/docker-build.yml
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Suggested next improvements

1. Add student phone/email verification and real SMS/WhatsApp notifications.
2. Add shop opening hours, holidays, and pause/resume queue controls.
3. Store estimated completion and actual completion timestamps to calibrate the model.
4. Add authentication and role-based access before deploying publicly.
5. Add rate limiting, input validation, backups, and a production database such as PostgreSQL.

## GitHub setup

Create a GitHub repository, then from this project directory:

```bash
git init
git add .
git commit -m "Initial Smart Queue Print Shop project"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

The GitHub Actions workflow will build the backend and frontend Docker images. It does not publish them to a registry; configure registry login and `push: true` if you want published images.
