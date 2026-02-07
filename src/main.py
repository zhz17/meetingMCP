from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from src.routers import api
from src.murals import router as murals_router
from src import ui

app = FastAPI(title="Meeting Booking")

# Include routers
# app.include_router(api.router, prefix="/auth", tags=["auth"])
# app.include_router(murals_router.router, prefix="/murals", tags=["murals"])

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return ui.html_dashboard

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
