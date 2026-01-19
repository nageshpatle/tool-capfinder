from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import sys

# Add current dir to sys.path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from optimizer import OptimizerService

from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Enable CORS (still useful for dev if running disjointly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Logic
LIBRARY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Murata_Unified_Library.csv") 
optimizer = OptimizerService(LIBRARY_PATH)

# Serve Frontend
# Path to frontend dir relative to this file: ../frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

# Mount /api first so it takes precedence
# (FastAPI matches in order, but separate paths don't conflict)


class OptimizeRequest(BaseModel):
    target_cap: float
    tolerance: float
    dc_bias: float
    max_count: int
    min_rated_volt: float
    min_temp: float
    conn_type: int
    packages: List[str]

@app.get("/api/packages")
def get_packages():
    """Return list of valid packages, sorted by area."""
    return optimizer.get_available_packages()

@app.post("/api/optimize")
def optimize_bank(req: OptimizeRequest):
    """Run optimization."""
    # Convert Pydantic model to dict
    constraints = req.dict()
    
    # Run
    results = optimizer.solve(constraints)
    
    return results

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "CapOptimizer Backend"}

# Mount Static Files (Catch-all)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
