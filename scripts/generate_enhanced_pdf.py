"""
ENHANCED PDF REPORT WITH RISK CONTEXT
======================================
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from datetime import datetime
import os

os.makedirs("outputs", exist_ok=True)

# Top 10 Value Plays (sorted by Value Score)
TOP_PLAYS = [
    {"rank": 1, "player": "Jonathan Taylor", "team": "IND", "prop": "Rush Yards", 
     "line": 70.5, "adj_proj": 145.5, "play": "OVER", "conf": 98, "risk": 4, "value": 58.8,
     "context": "JAX #22 run D + HOT trend + 85% consistency"},
    {"rank": 2, "player": "Jonathan Taylor", "team": "IND", "prop": "TDs",
     "line": 0.5, "adj_proj": 1.9, "play": "OVER", "conf": 98, "risk": 4, "value": 58.8,
     "context": "JAX #28 red zone D + 17 TDs this season"},
    {"rank": 3, "player": "T.J. Watt", "team": "PIT", "prop": "Sacks",
     "line": 0.5, "adj_proj": 1.1, "play": "OVER", "conf": 98, "risk": 5, "value": 49.0,
     "context": "CLE allows 42 sacks + Winston holds ball"},
    {"rank": 4, "player": "Myles Garrett", "team": "CLE", "prop": "Sacks",
     "line": 0.5, "adj_proj": 0.9, "play": "OVER", "conf": 98, "risk": 5, "value": 49.0,
     "context": "Elite pass rusher + 78% consistency"},
    {"rank": 5, "player": "Brian Thomas", "team": "JAX", "prop": "Rec Yards",
     "line": 65.5, "adj_proj": 89.8, "play": "OVER", "conf": 98, "risk": 5, "value": 49.0,
     "context": "ROTY candidate + IND #26 pass D"},
    {"rank": 6, "player": "David Njoku", "team": "CLE", "prop": "Rec Yards",
     "line": 35.5, "adj_proj": 48.3, "play": "OVER", "conf": 97, "risk": 5, "value": 48.7,
     "context": "Winston's safety valve + garbage time"},
    {"rank": 7, "player": "Zaire Franklin", "team": "IND", "prop": "Tackles",
     "line": 6.5, "adj_proj": 7.6, "play": "OVER", "conf": 79, "risk": 4, "value": 47.3,
     "context": "Tackle machine + 82% consistency"},
    {"rank": 8, "player": "Jerry Jeudy", "team": "CLE", "prop": "Rec Yards",
     "line": 45.5, "adj_proj": 57.6, "play": "OVER", "conf": 93, "risk": 5, "value": 46.3,
     "context": "Winston's #1 target when trailing"},
    {"rank": 9, "player": "Michael Pittman", "team": "IND", "prop": "Rec Yards",
     "line": 44.5, "adj_proj": 53.7, "play": "OVER", "conf": 83, "risk": 5, "value": 41.7,
     "context": "JAX secondary exploitable"},
    {"rank": 10, "player": "George Pickens", "team": "PIT", "prop": "Rec Yards",
     "line": 60.5, "adj_proj": 71.0, "play": "OVER", "conf": 80, "risk": 5, "value": 39.9,
     "context": "PIT's WR1 + CLE avg secondary"},
]

SLAM_UNDERS = [
    {"player": "Travis Etienne", "team": "JAX", "prop": "Rush Yards",
     "line": 67.5, "adj_proj": 26.8, "play": "UNDER", "conf": 98, "risk": 9,
     "context": "LOST JOB to Bigsby (47.9 avg) - only gets 37.2"},
    {"player": "Nick Chubb", "team": "CLE", "prop": "Rush Yards",
     "line": 45.5, "adj_proj": 14.5, "play": "UNDER", "conf": 98, "risk": 10,
     "context": "POST-INJURY + PIT #3 run D + pitch count"},
    {"player": "Travis Etienne", "team": "JAX", "prop": "Rush+Rec",
     "line": 85.5, "adj_proj": 38.9, "play": "UNDER", "conf": 98, "risk": 9,
     "context": "Total involvement cratered with Bigsby takeover"},
    {"player": "Trevor Lawrence", "team": "JAX", "prop": "Pass Yards",
     "line": 246.5, "adj_proj": 159.5, "play": "UNDER", "conf": 95, "risk": 8,
     "context": "QUESTIONABLE status + 204.5 avg when healthy"},
]


def create_title_page(pdf):
    """Enhanced title page"""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 8.5)
    ax.axis('off')
    
    ax.text(5.5, 7.5, "UNDERDOG FANTASY", fontsize=32, ha='center', 
            fontweight='bold', color='#1a1a2e')
    ax.text(5.5, 6.7, "ENHANCED RISK-ADJUSTED ANALYSIS", fontsize=20, ha='center',
            fontweight='bold', color='#4a4a6a')
    
    ax.text(5.5, 5.8, "PIT @ CLE  |  JAX @ IND", fontsize=16, ha='center', color='#333')
    ax.text(5.5, 5.3, f"Sunday, December 28, 2025", fontsize=14, ha='center', color='#666')
    
    # Analysis layers box
    layers_text = """
ANALYSIS LAYERS INCLUDED:
    
    Season Averages (Base Stats)
    Matchup Factors (Opponent Defense Rankings)
    Game Script (Spread, Pace, Blowout Risk)
    Recent Form (Last 3 Games Trend)
    Situational (Weather, Home/Away)
    Health Status (Injuries)
    Consistency Rating (Hit Rate %)
    Risk Assessment (1-10 Scale)
    Value Score (Confidence x Safety)
    """
    
    ax.text(0.8, 4.5, layers_text, fontsize=11, va='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='lightcyan', alpha=0.5))
    
    # Lock of the day
    ax.add_patch(plt.Rectangle((3, 1.5), 5, 1.5, facecolor='gold', alpha=0.3, edgecolor='black'))
    ax.text(5.5, 2.7, "LOCK OF THE DAY", fontsize=14, ha='center', fontweight='bold')
    ax.text(5.5, 2.2, "Jonathan Taylor OVER 70.5 Rush Yards", fontsize=12, ha='center')
    ax.text(5.5, 1.8, "Adj Proj: 145.5 | Conf: 98% | Risk: 4/10 | Value: 58.8", 
            fontsize=10, ha='center', color='#333')
    
    ax.text(5.5, 0.5, "Based on 2024 Pro-Football-Reference Stats + Contextual Analysis", 
            fontsize=9, ha='center', color='gray')
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def create_top10_page(pdf):
    """Top 10 value plays with context"""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis('off')
    
    ax.text(0.5, 0.97, "TOP 10 VALUE PLAYS", fontsize=22, 
            ha='center', va='top', fontweight='bold', transform=ax.transAxes)
    ax.text(0.5, 0.93, "Ranked by Value Score (Confidence x Safety)", fontsize=12,
            ha='center', va='top', color='gray', transform=ax.transAxes)
    
    # Create table manually
    y_start = 0.88
    row_height = 0.075
    
    # Headers
    headers = ["#", "Player", "Team", "Prop", "Line", "Proj", "Play", "Conf", "Risk", "Value"]
    col_x = [0.03, 0.08, 0.28, 0.35, 0.48, 0.56, 0.66, 0.74, 0.82, 0.90]
    
    for i, (header, x) in enumerate(zip(headers, col_x)):
        ax.text(x, y_start, header, fontsize=10, fontweight='bold', transform=ax.transAxes)
    
    ax.plot([0.02, 0.98], [y_start - 0.015, y_start - 0.015], 
            color='black', linewidth=1.5, transform=ax.transAxes)
    
    # Data rows
    for idx, play in enumerate(TOP_PLAYS):
        y = y_start - 0.025 - (idx * row_height)
        
        # Alternating background
        if idx % 2 == 0:
            rect = plt.Rectangle((0.02, y - 0.02), 0.96, row_height - 0.01,
                                 facecolor='lightgray', alpha=0.2, transform=ax.transAxes)
            ax.add_patch(rect)
        
        # Data
        data = [
            str(play["rank"]),
            play["player"][:15],
            play["team"],
            play["prop"][:10],
            str(play["line"]),
            f"{play['adj_proj']:.1f}",
            play["play"],
            f"{play['conf']}%",
            str(play["risk"]),
            f"{play['value']:.1f}"
        ]
        
        for i, (val, x) in enumerate(zip(data, col_x)):
            color = 'green' if val == 'OVER' else ('red' if val == 'UNDER' else 'black')
            weight = 'bold' if i in [0, 6, 9] else 'normal'
            ax.text(x, y, val, fontsize=9, color=color, fontweight=weight, transform=ax.transAxes)
        
        # Context line (smaller)
        ax.text(0.08, y - 0.025, play["context"], fontsize=7, color='gray', 
                style='italic', transform=ax.transAxes)
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def create_risk_chart_page(pdf):
    """Risk vs Confidence scatter with value sizing"""
    fig = plt.figure(figsize=(11, 8.5))
    
    # Main scatter plot
    ax1 = fig.add_subplot(121)
    
    all_plays = TOP_PLAYS + SLAM_UNDERS
    
    confs = [p["conf"] for p in all_plays]
    risks = [p["risk"] for p in all_plays]
    values = [p.get("value", p["conf"] * (10 - p["risk"]) / 10) for p in all_plays]
    colors = ['green' if p["play"] == "OVER" else 'red' for p in all_plays]
    
    scatter = ax1.scatter(risks, confs, s=[v*5 for v in values], c=colors, alpha=0.6, edgecolors='black')
    
    # Add labels
    for i, play in enumerate(all_plays):
        ax1.annotate(play["player"].split()[0], (risks[i], confs[i]), 
                    fontsize=7, ha='center', va='bottom')
    
    ax1.set_xlabel("Risk Score (1-10, lower = safer)", fontsize=10)
    ax1.set_ylabel("Confidence %", fontsize=10)
    ax1.set_title("Risk vs Confidence\n(Size = Value Score)", fontsize=12, fontweight='bold')
    ax1.set_xlim(0, 11)
    ax1.set_ylim(0, 100)
    ax1.axhline(y=70, color='gray', linestyle='--', alpha=0.5, label='70% confidence threshold')
    ax1.axvline(x=6, color='gray', linestyle='--', alpha=0.5, label='Risk threshold')
    
    # Quadrant labels
    ax1.text(3, 85, "SAFE SLAMS", fontsize=10, color='green', fontweight='bold', ha='center')
    ax1.text(8, 85, "RISKY BETS", fontsize=10, color='orange', fontweight='bold', ha='center')
    ax1.text(3, 30, "SKIP", fontsize=10, color='gray', fontweight='bold', ha='center')
    ax1.text(8, 30, "AVOID", fontsize=10, color='red', fontweight='bold', ha='center')
    
    # Value bar chart
    ax2 = fig.add_subplot(122)
    
    top5 = sorted(all_plays, key=lambda x: x.get("value", 0), reverse=True)[:8]
    names = [f"{p['player'][:10]}\n{p['play']}" for p in top5]
    vals = [p.get("value", p["conf"] * (10 - p["risk"]) / 10) for p in top5]
    bar_colors = ['green' if p["play"] == "OVER" else 'red' for p in top5]
    
    bars = ax2.barh(range(len(names)), vals, color=bar_colors, alpha=0.7, edgecolor='black')
    ax2.set_yticks(range(len(names)))
    ax2.set_yticklabels(names, fontsize=9)
    ax2.set_xlabel("Value Score", fontsize=10)
    ax2.set_title("Top 8 Value Plays", fontsize=12, fontweight='bold')
    ax2.invert_yaxis()
    
    for i, (bar, val) in enumerate(zip(bars, vals)):
        ax2.text(val + 1, bar.get_y() + bar.get_height()/2, f"{val:.1f}", 
                va='center', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def create_game_script_page(pdf):
    """Game script breakdown"""
    fig, axes = plt.subplots(1, 2, figsize=(11, 8.5))
    
    # Game 1: PIT @ CLE
    ax1 = axes[0]
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 10)
    ax1.axis('off')
    ax1.set_title("PIT @ CLE Game Script", fontsize=14, fontweight='bold', pad=20)
    
    pit_cle_text = """
SPREAD: Steelers -7.5
TOTAL: 42.5 (LOW)
PREDICTED: PIT 24 - CLE 17

GAME FLOW: PIT CONTROL
PACE: SLOW

KEY FACTORS:
- PIT will run clock with lead
- CLE O-line allows 42 sacks
- Jameis turnover machine
- Cold, physical game expected

PIT BOOSTS:
  Rush volume +15%
  Pass volume -8%
  T.J. Watt feast game

CLE ADJUSTMENTS:
  Abandoning run early
  Pass volume +15%
  Garbage time stats likely

DEFENSE MATCHUPS:
  CLE Rush D: #20 (WEAK)
  CLE Pass D: #15 (AVG)
  PIT Rush D: #3 (ELITE)
  PIT Pass D: #8 (STRONG)
"""
    ax1.text(0.5, 0.95, pit_cle_text, fontsize=10, va='top', 
             fontfamily='monospace', transform=ax1.transAxes,
             bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
    
    # Game 2: JAX @ IND
    ax2 = axes[1]
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 10)
    ax2.axis('off')
    ax2.set_title("JAX @ IND Game Script", fontsize=14, fontweight='bold', pad=20)
    
    jax_ind_text = """
SPREAD: Colts -3.5
TOTAL: 45.5 (MODERATE)
PREDICTED: IND 27 - JAX 21

GAME FLOW: COMPETITIVE
PACE: MODERATE

KEY FACTORS:
- IND leaning on JT heavy
- JAX QB situation murky
- Higher scoring game
- Dome = no weather issues

IND BOOSTS:
  JT rush volume +15%
  Red zone dominance expected
  Pass optional

JAX ADJUSTMENTS:
  Etienne role REDUCED
  Bigsby now lead back
  May need to throw late

DEFENSE MATCHUPS:
  JAX Rush D: #22 (WEAK)
  JAX Pass D: #26 (BAD)
  JAX Red Zone D: #28 (AWFUL)
  IND Rush D: #18 (AVG)
  IND Pass D: #12 (SOLID)
"""
    ax2.text(0.5, 0.95, jax_ind_text, fontsize=10, va='top',
             fontfamily='monospace', transform=ax2.transAxes,
             bbox=dict(boxstyle='round', facecolor='lightcyan', alpha=0.5))
    
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def create_unders_page(pdf):
    """Strong UNDER plays"""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis('off')
    
    ax.text(0.5, 0.95, "SLAM UNDER PLAYS", fontsize=22, 
            ha='center', va='top', fontweight='bold', color='red', transform=ax.transAxes)
    ax.text(0.5, 0.90, "Lines Set Too High - Value in UNDER", fontsize=12,
            ha='center', va='top', color='gray', transform=ax.transAxes)
    
    y = 0.82
    for play in SLAM_UNDERS:
        # Player box
        rect = plt.Rectangle((0.05, y - 0.12), 0.9, 0.14, facecolor='mistyrose', 
                             alpha=0.5, edgecolor='red', transform=ax.transAxes)
        ax.add_patch(rect)
        
        ax.text(0.08, y, f"{play['player']} ({play['team']})", fontsize=14, 
                fontweight='bold', transform=ax.transAxes)
        ax.text(0.08, y - 0.03, f"{play['prop']}: UNDER {play['line']}", 
                fontsize=12, transform=ax.transAxes)
        ax.text(0.08, y - 0.06, f"Adjusted Projection: {play['adj_proj']:.1f}", 
                fontsize=11, color='red', fontweight='bold', transform=ax.transAxes)
        ax.text(0.08, y - 0.09, f"Context: {play['context']}", 
                fontsize=9, color='gray', style='italic', transform=ax.transAxes)
        
        ax.text(0.85, y - 0.03, f"Risk: {play['risk']}/10", fontsize=10, 
                ha='center', transform=ax.transAxes)
        ax.text(0.85, y - 0.06, f"Conf: {play['conf']}%", fontsize=10,
                ha='center', fontweight='bold', transform=ax.transAxes)
        
        y -= 0.18
    
    # Warning box
    ax.text(0.5, 0.12, "WARNING: Nick Chubb & Etienne are HIGH RISK due to role changes\n"
            "But the edge is MASSIVE - worth the risk at these inflated lines",
            fontsize=10, ha='center', transform=ax.transAxes,
            bbox=dict(boxstyle='round', facecolor='lightyellow', edgecolor='orange'))
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def create_cheatsheet_page(pdf):
    """Final cheat sheet"""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis('off')
    
    ax.text(0.5, 0.97, "SUNDAY CHEAT SHEET", fontsize=24, 
            ha='center', va='top', fontweight='bold', transform=ax.transAxes)
    
    cheatsheet = """
=========================================================
           SAFEST PLAYS (Risk 4-5 / High Value)
=========================================================
    
    1. JT OVER 70.5 Rush      [Proj 145] Conf 98% Risk 4
    2. JT OVER 0.5 TDs        [Proj 1.9] Conf 98% Risk 4
    3. Watt OVER 0.5 Sacks    [Proj 1.1] Conf 98% Risk 5
    4. Garrett OVER 0.5 Sacks [Proj 0.9] Conf 98% Risk 5
    5. B.Thomas OVER 65.5 Rec [Proj 90]  Conf 98% Risk 5
    6. Njoku OVER 35.5 Rec    [Proj 48]  Conf 97% Risk 5
    
=========================================================
              VALUE UNDERS (High Edge)
=========================================================
    
    1. Etienne UNDER 67.5 Rush  [Proj 27] - SLAM
    2. Etienne UNDER 85.5 R+R   [Proj 39] - SLAM
    3. Chubb UNDER 45.5 Rush    [Proj 15] - RISKY
    4. T.Lawrence UNDER 246.5   [Proj 160] - IF HEALTHY
    
=========================================================
                PARLAY SUGGESTIONS
=========================================================
    
    SAFE 3-LEG:
    JT OVER 70.5 + Watt Sack + Garrett Sack
    
    VALUE 4-LEG:
    JT TD + B.Thomas OVER 65.5 + Njoku OVER 35.5 + Pickens OVER 60.5
    
    RISKY 5-LEG (High Payout):
    JT OVER 70.5 + Etienne UNDER 67.5 + Watt Sack + 
    Garrett Sack + B.Thomas OVER 65.5

=========================================================
"""
    
    ax.text(0.08, 0.90, cheatsheet, fontsize=10, va='top',
            fontfamily='monospace', transform=ax.transAxes,
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    
    ax.text(0.5, 0.05, f"Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", 
            fontsize=10, ha='center', color='gray', transform=ax.transAxes)
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def main():
    pdf_path = "outputs/enhanced_props_report.pdf"
    
    print("Generating Enhanced PDF Report...")
    print("=" * 50)
    
    with PdfPages(pdf_path) as pdf:
        print("  Page 1: Title & Overview...")
        create_title_page(pdf)
        
        print("  Page 2: Top 10 Value Plays...")
        create_top10_page(pdf)
        
        print("  Page 3: Risk vs Confidence Charts...")
        create_risk_chart_page(pdf)
        
        print("  Page 4: Game Script Breakdown...")
        create_game_script_page(pdf)
        
        print("  Page 5: Slam Under Plays...")
        create_unders_page(pdf)
        
        print("  Page 6: Cheat Sheet...")
        create_cheatsheet_page(pdf)
    
    print("=" * 50)
    print(f"PDF saved to: {pdf_path}")
    print(f"Total pages: 6")


if __name__ == "__main__":
    main()
