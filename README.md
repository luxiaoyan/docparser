# PDF Document Parser

PDF-only document parsing service with upload, preflight, unified parse results, schema-based field extraction, and a small web console.

## Setup

Install `uv` first if it is not already available:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Create the virtual environment and install locked project dependencies:

```powershell
uv python install 3.12
uv sync
```

## Test

```powershell
uv run pytest
```

## Run API

```powershell
uv run uvicorn docparser.app:app --reload
```

Open `http://127.0.0.1:8000/` to use the web console.

The milestone-2 parser exposes a MinerU-compatible boundary. Set `DOCPARSER_MINERU_COMMAND` to a command that accepts `{input}` and returns parse JSON on stdout. When it is not configured, the service uses a PyMuPDF native-text fallback and includes a warning in the parse result.

For production-style deployments, run MinerU's API service and point the main service at its synchronous parse endpoint:

```powershell
uv pip install -U "mineru[all]"
uv run mineru-api --host 127.0.0.1 --port 8001
```

Then start the main API with the full `mineru-api` endpoint:

```powershell
$env:DOCPARSER_MINERU_SERVICE_URL="http://127.0.0.1:8001/file_parse"
uv run uvicorn docparser.app:app --host 127.0.0.1 --port 8000
```

`DOCPARSER_MINERU_SERVICE_URL` is the full HTTP request URL used by the main service. For `mineru-api`, use `/file_parse`; the main service sends a `multipart/form-data` POST with the PDF file field named `files`, plus MinerU return flags.

For Docker Compose, configure the same value through the environment. If `mineru-api` runs as a Compose service named `mineru-service`, use the service DNS name:

```powershell
$env:DOCPARSER_MINERU_SERVICE_URL="http://mineru-service:8000/file_parse"
docker compose up --build -d
```

If the main API runs in Docker but `mineru-api` runs on the host machine, use `http://host.docker.internal:8001/file_parse`.

If `DOCPARSER_MINERU_SERVICE_URL` is configured, it takes precedence over the local command adapter.

To run the local service with a local MinerU command instead:

```powershell
uv pip install -U "mineru[all]"
$env:DOCPARSER_MINERU_COMMAND=".venv/bin/python scripts/mineru_adapter.py {input}"
uv run uvicorn docparser.app:app --host 127.0.0.1 --port 8001
```

## Schema Extraction

Create or update a schema:

```powershell
curl -X POST http://127.0.0.1:8000/schemas `
  -H "Content-Type: application/json" `
  -d '{"schema_id":"contract_v1","name":"合同字段抽取","fields":[{"name":"contract_no","label":"合同编号","type":"string","required":true,"strategies":[{"type":"regex","pattern":"合同编号[:：\\s]*([A-Za-z0-9\\-]+)"},{"type":"regex","pattern":"Contract No[:：\\s]*([A-Za-z0-9\\-]+)"}]}]}'
```

Run extraction after uploading a PDF:

```powershell
curl -X POST http://127.0.0.1:8000/documents/<document_id>/extract `
  -H "Content-Type: application/json" `
  -d '{"schema_id":"contract_v1"}'

curl http://127.0.0.1:8000/extractions/<extraction_id>
```

Supported deterministic strategies are `form_field`, `regex`, `keyword`, and `table_column`.

## Docker Deploy

```powershell
docker compose up --build -d
curl http://127.0.0.1:8000/health
```

Open `http://127.0.0.1:8000/` after the container is running.

The API requires `fastapi`, `uvicorn`, and `python-multipart`. If those packages are not installed, `docparser.app:create_app` raises a clear missing dependency error.
