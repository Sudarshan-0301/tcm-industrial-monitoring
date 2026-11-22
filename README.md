# TCM Vercel migration
This is a migration starter for a Next.js frontend, FastAPI inference API and Supabase database.

## Deploy frontend
Import `frontend/` as the Vercel project root. Framework: Next.js. Add `NEXT_PUBLIC_TCM_API_URL` pointing to the deployed API base URL.

## Deploy API
Deploy `backend/` as a separate Vercel Python Function project with `backend/` as root. Set:
- `MODEL_PATH` to the path of the securely supplied model artifact in the API runtime.
- `TCM_APP_TOKEN` to a long random secret (optional in local dev; recommended in production).
- `FRONTEND_ORIGIN` to the exact Vercel frontend origin.
Do not commit the `.joblib` model to a public repository. For Vercel, note function package and execution limits; a model binary of this size must be tested in the selected deployment plan. If package size or runtime limits are exceeded, host FastAPI on a Python service such as Render/Railway instead.

## Model compatibility
The supplied model was previously reported as serialized with scikit-learn 1.6.1. Backend pins 1.6.1. The API preserves the original `utils/model.py` feature names and extraction: mean, std, RMS, peak-to-peak, median, p90_p10, 512-row windows, majority vote. Prediction has not yet been smoke-tested against labelled recordings in this migration.

## Database
Run `supabase/schema.sql` in Supabase SQL Editor. This schema is an initial base; secure RLS policies and database RPC timer functions must be added and tested before production data is stored. Do not expose service-role keys in frontend code.

## Current migration scope
The frontend provides a responsive dashboard, file analysis endpoint, and classifier endpoint. Tool timer UI is intentionally disabled until server-side timer RPCs and secure persistence are implemented. Do not treat this as production-ready yet.
