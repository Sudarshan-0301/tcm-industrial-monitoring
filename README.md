# TCM Industrial Monitoring

Starter application for the MEcon MD-3030-EN retrofit multi-sensor tool condition monitoring project.

## Included
- Industrial-style Streamlit dashboard
- CSV / Excel upload and sensor channel plotting
- Tool registration and single-operator manual timer interface
- Supabase schema for tools, machining sessions, recordings and inspections
- Model artifact presence check

## Important current limitations
- `TCM_Model.joblib` is included in this ZIP for local testing. It is intentionally ignored by Git because model binaries should not be committed to a public repository.
- New/Old-Worn inference is integrated using 512-row non-overlapping windows and the model's stored sensor/feature schema. Incomplete trailing rows are ignored. Majority vote share is displayed as agreement, not probability or accuracy.
- Timer transitions use database RPC functions to accumulate active cutting intervals across pause/resume. Test the SQL on a separate Supabase project before operational use.
- This application analyses uploaded files; it does not stream live CNC data.
- Do not expose Supabase service-role credentials in client code or a public repository.

## Run locally
1. Install Python 3.10 or later.
2. Create a virtual environment.
3. Install requirements: `pip install -r requirements.txt`
4. Create `.streamlit/secrets.toml` from `.streamlit/secrets.toml.example`.
5. Create a Supabase project and run `supabase_schema.sql` in its SQL Editor.
6. Start: `streamlit run app.py`

## Deploy
1. Push this folder to a private GitHub repository.
2. In Streamlit Community Cloud, deploy the repository and select `app.py`.
3. Add `SUPABASE_URL` and `SUPABASE_KEY` in app Secrets.
4. Add the model artifact through a secure deployment mechanism after the inference pipeline is validated.

## Before operational use
- Add authentication / network protection.
- Use database-side RPC functions for atomic timer state transitions and exact accumulated cutting-time calculations.
- Test browser refresh, disconnection, pause/resume, duplicate clicks and concurrent requests.
- Back up database and recordings.

## Model compatibility
The supplied `TCM_Model.joblib` was serialized with scikit-learn 1.6.1. The requirements file pins scikit-learn to 1.6.1 to avoid incompatible deserialization with newer releases. Keep this version aligned when deploying.
