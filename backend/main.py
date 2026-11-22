import os, io, hashlib
from datetime import datetime, timezone
from typing import Optional
import joblib, numpy as np, pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI(title="TCM API", version="1.0.0")
FRONTEND_ORIGIN=os.getenv("FRONTEND_ORIGIN","*")
APP_TOKEN=os.getenv("TCM_APP_TOKEN","")
MODEL_PATH=os.getenv("MODEL_PATH","/var/task/TCM_Model.joblib")
app.add_middleware(CORSMiddleware,allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN!="*" else ["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])

def auth(authorization: Optional[str]):
    if APP_TOKEN and authorization != f"Bearer {APP_TOKEN}":
        raise HTTPException(401,"Unauthorized")

def parse_upload(name, raw):
    low=name.lower()
    try:
        if low.endswith(".csv"): df=pd.read_csv(io.BytesIO(raw))
        elif low.endswith(".xlsx"): df=pd.read_excel(io.BytesIO(raw),engine="openpyxl")
        elif low.endswith(".xls"): df=pd.read_excel(io.BytesIO(raw))
        else: raise HTTPException(400,"Supported files: CSV, XLSX, XLS")
    except Exception as e:
        if isinstance(e,HTTPException): raise
        raise HTTPException(400,f"Unable to read file: {e}")
    df.columns=[str(c).strip() for c in df.columns]
    return df

@app.get("/health")
def health():
    return {"status":"ok","model_available":os.path.exists(MODEL_PATH)}

@app.post("/analyze")
async def analyze(file: UploadFile=File(...), authorization: Optional[str]=Header(None)):
    auth(authorization)
    raw=await file.read()
    df=parse_upload(file.filename or "upload.csv",raw)
    sensors=["spindle_vib","platform_vib","spindle_temp","platform_temp","spindle_force","acoustic_level","x_current","y_current","z_current","spindle_current"]
    present=[c for c in sensors if c in df.columns]
    result={"filename":file.filename,"sha256":hashlib.sha256(raw).hexdigest(),"rows":len(df),"columns":list(df.columns),
            "sensors":present,"missing_sensors":[c for c in sensors if c not in df.columns],
            "preview":df.head(10).replace({np.nan:None}).to_dict(orient="records")}
    return result

@app.post("/classify")
async def classify(file: UploadFile=File(...), authorization: Optional[str]=Header(None)):
    auth(authorization)
    if not os.path.exists(MODEL_PATH): raise HTTPException(503,"Model artifact is not configured on the API host.")
    raw=await file.read()
    df=parse_upload(file.filename or "upload.csv",raw)
    bundle=joblib.load(MODEL_PATH)
    if not isinstance(bundle,dict): raise HTTPException(500,"Unsupported model bundle.")
    model=bundle.get("pipeline",bundle.get("model"))
    feature_columns=bundle.get("feature_columns")
    sensors=bundle.get("sensor_columns",[])
    window_size=int(bundle.get("window_size",512))
    if model is None or not feature_columns: raise HTTPException(500,"Model bundle missing pipeline/model or feature_columns.")
    missing=[c for c in sensors if c not in df.columns]
    if missing: raise HTTPException(400,"Missing required sensor columns: "+", ".join(missing))
    rows=[]
    for start in range(0,len(df)-window_size+1,window_size):
        chunk=df.iloc[start:start+window_size]
        feats={}
        for col in sensors:
            x=pd.to_numeric(chunk[col],errors="coerce").dropna().to_numpy()
            if len(x)==0: continue
            feats[f"{col}_mean"]=float(np.mean(x))
            feats[f"{col}_std"]=float(np.std(x))
            feats[f"{col}_rms"]=float(np.sqrt(np.mean(x*x)))
            feats[f"{col}_ptp"]=float(np.ptp(x))
            feats[f"{col}_median"]=float(np.median(x))
            feats[f"{col}_p90_p10"]=float(np.percentile(x,90)-np.percentile(x,10))
        rows.append(feats)
    if not rows: raise HTTPException(400,f"At least {window_size} rows are required.")
    X=pd.DataFrame(rows).reindex(columns=feature_columns,fill_value=0)
    preds=model.predict(X)
    counts=pd.Series(preds).value_counts()
    winner=counts.idxmax()
    label={0:"New",1:"Old / Worn"}.get(int(winner),str(winner))
    agreement=float(counts.max()/counts.sum()*100)
    return {"classification":label,"agreement_percent":round(agreement,2),"windows":len(preds),
            "note":"Window majority agreement is not calibrated probability, model confidence, or accuracy.",
            "sha256":hashlib.sha256(raw).hexdigest()}
