from fastapi import FastAPI

app = FastAPI(title="Pharmacy IMS API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "pharmacy-ims-backend", "version": app.version}
