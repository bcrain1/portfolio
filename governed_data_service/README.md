# Governed Data Service

Review data corrections without losing history or exposing a half-published dataset. An analyst proposes a create, update, or soft delete; a separate reviewer decides it; an approved mutation creates an audit event and a new immutable Parquet snapshot.



## Run locally

Use tested Python 3.12 and a virtual environment. From this directory:

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:GDS_DATA_DIR = "runtime"
python -m uvicorn app:create_app --factory --host 127.0.0.1 --port 8000
```

### macOS / Linux

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export GDS_DATA_DIR=runtime
python -m uvicorn app:create_app --factory --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. `create_app(data_dir=None)` resolves `GDS_DATA_DIR` when set, otherwise uses `runtime/data` beneath this project. Use a writable local directory; never point it at employer or personal data.

The UI selector sends one intentionally impersonable local identity in `X-Demo-User`: `viewer` reads, `analyst` submits proposals, `reviewer` decides another author’s proposal, and `admin` advances migrations. It is a teaching device, not authentication.

## Demo flow

1. As `analyst`, submit an update using a record’s displayed revision.
2. As `reviewer`, approve it with a reason; then refresh the audit trail and snapshot pointer.
3. As `admin`, advance expand, backfill, and contract in order.
4. During coexistence, compare `GET /api/records?client_version=1` and `client_version=2`.

Run targeted local verification with `python -B -m unittest discover -s tests -v`. Read the [data contract](docs/DATA_CONTRACT.md), [architecture](docs/ARCHITECTURE.md), [owner walkthrough](docs/OWNER_WALKTHROUGH.md), and generated [case-study PDF](output/Brandon_Crain_Governed_Data_Service.pdf).

## Limits

The design does not claim production IAM, cloud durability, tamper-proof auditing, multi-host coordination, or arbitrary transactional Parquet updates. Local OS/filesystem and SQLite durability limits apply. A crash before the SQLite commit may leave unreferenced files; they are never published or automatically deleted. Verification evidence and any test counts belong in the generated validation material after actual runs.

## Implementation notes

Equipment inspections and business rules are synthetic. The service runs on a single host and contains no employer code or data. Development used AI assistance; the source, tests and walkthrough document the implementation and its limits.

