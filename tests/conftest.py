import os
import sys
from pathlib import Path

# Make the repo root importable so tests can import the app modules directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tests always run the app in self-host (BYOK) mode. app.py freezes
# BILLING_ENABLED at import time and load_dotenv never overrides an existing
# variable, so this must be set here — before any test module imports app — or
# the suite's behavior would depend on the developer's personal .env.
os.environ["BILLING_ENABLED"] = "0"

# MAPA ROTO Clip intentionally ships only the MIT/self-host core. Upstream's
# separately licensed cloud package is not part of this fork, so its unit tests
# must not be collected in the public/local build.
if not (Path(__file__).resolve().parents[1] / "cloud").is_dir():
    collect_ignore = [
        "test_account_erasure.py",
        "test_alert_classify.py",
        "test_api_keys.py",
        "test_billing_states.py",
        "test_email_policy.py",
        "test_job_error_text.py",
        "test_mcp_oauth.py",
        "test_metering_free_plan.py",
        "test_openpanel_revenue.py",
        "test_partial_processing.py",
        "test_proxy_ledger.py",
        "test_proxy_watch.py",
        "test_subtitle_metering.py",
    ]
