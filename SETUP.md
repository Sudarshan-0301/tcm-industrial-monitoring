# Beginner setup guide

## A. Create the database
1. Open Supabase and create a project.
2. Open SQL Editor.
3. Paste the contents of `supabase_schema.sql` and run it.
4. Copy the project URL and API key.
5. For a public deployment, do not use an unrestricted public database policy. This prototype uses server-side credentials; add a protected backend or server-only key handling before exposing write operations publicly.

## B. Add secrets locally
1. Rename `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
2. Paste your Supabase URL and key.
3. Never upload this file to GitHub.

## C. Add the classifier
Place the exact `TCM_Model.joblib` bundle in the same folder as `app.py`. The code expects a dictionary containing `pipeline`, `feature_columns`, `sensor_columns`, and `window_size`, consistent with the described project notebook. If your artifact differs, it must be adapted and tested before claiming integration.

## D. Run
```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

## E. GitHub
Create a new private repository, extract this ZIP, then upload the project files or use Git:
```bash
git init
git add .
git commit -m "Initial TCM monitoring application"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

## F. Deploy
Deploy the repository through Streamlit Community Cloud. Set `app.py` as the main file and add `SUPABASE_URL` and `SUPABASE_ANON_KEY` in app secrets. Do not deploy until database permissions and secrets are reviewed.
