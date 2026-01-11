from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from ufa.models.schemas import RankRequest, RankResponse, RankedPick, BuildRequest, BuildResponse, EntryOut
from ufa.analysis.prob import prob_hit
from ufa.analysis.payouts import power_table, flex_table
from ufa.optimizer.entry_builder import build_entries
from ufa.config import settings

# Import SaaS routers
from ufa.api.auth import router as auth_router
from ufa.api.payments import router as payments_router
from ufa.api.signals import router as signals_router
from ufa.api.webhooks import router as webhooks_router
from ufa.api.admin import router as admin_router

load_dotenv()
app = FastAPI(
    title="Underdog Signals API", 
    version="1.0.0",
    description="Sports prop betting signals powered by Monte Carlo simulation"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include SaaS routers
app.include_router(auth_router)
app.include_router(payments_router)
app.include_router(signals_router)
app.include_router(webhooks_router)
app.include_router(admin_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/rank", response_model=RankResponse)
def rank(req: RankRequest):
    ranked = []
    for i, p in enumerate(req.picks):
        try:
            p_hit = prob_hit(p.line, p.direction, recent_values=p.recent_values, mu=p.mu, sigma=p.sigma)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Pick #{i} error: {e}")
        ranked.append(RankedPick(
            id=i, league=p.league, player=p.player, team=p.team,
            stat=p.stat, line=p.line, direction=p.direction, p_hit=round(float(p_hit), 4)
        ))
    ranked.sort(key=lambda x: x.p_hit, reverse=True)
    return RankResponse(format=req.format, ranked=ranked)

@app.post("/build", response_model=BuildResponse)
def build(req: BuildRequest):
    if req.legs < 2 or req.legs > settings.max_legs:
        raise HTTPException(status_code=400, detail=f"legs must be 2..{settings.max_legs}")

    table = power_table() if req.format == "power" else flex_table()

    ranked = []
    for i, p in enumerate(req.picks):
        p_hit = prob_hit(p.line, p.direction, recent_values=p.recent_values, mu=p.mu, sigma=p.sigma)
        ranked.append({
            "id": i, "league": p.league, "player": p.player, "team": p.team,
            "stat": p.stat, "line": p.line, "direction": p.direction, "p_hit": float(p_hit),
        })

    entries_raw = build_entries(
        picks=ranked,
        payout_table=table,
        legs=req.legs,
        min_teams=req.min_teams,
        max_entries=req.max_entries,
        same_team_penalty=req.same_team_penalty,
    )

    entries = [EntryOut(
        legs=e["legs"], teams=e["teams"], players=e["players"],
        p_list=e["p_list"], ev_units=e["ev_units"]
    ) for e in entries_raw]

    return BuildResponse(format=req.format, legs=req.legs, entries=entries)
