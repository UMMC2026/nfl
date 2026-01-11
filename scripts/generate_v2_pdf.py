"""
UNDERDOG FANTASY v2.0 - PDF REPORT GENERATOR
=============================================
Strategic Intelligence Report with all upgrades
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, FancyBboxPatch
import numpy as np
from datetime import datetime
import os

# Create outputs directory
os.makedirs("outputs", exist_ok=True)

# ============================================================================
# ALL ANALYZED PICKS DATA (from analysis_v2)
# ============================================================================
ANALYZED_PICKS = [
    # SLAM OVERS
    {"player": "Jonathan Taylor", "stat": "Rush Yards", "line": 70.5, "proj": 120.6, 
     "edge": 50.1, "edge_pct": 71.1, "hit_rate": 100, "value": 100, "play": "OVER ✅", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "JAX #28 Rush D", "priority": "SLAM"},
    {"player": "Jonathan Taylor", "stat": "Rush+Rec TDs", "line": 0.5, "proj": 0.9, 
     "edge": 0.4, "edge_pct": 82.4, "hit_rate": 73, "value": 100, "play": "OVER ✅", 
     "trend": "📉", "cons": "⚡", "opp": "JAX #28 Red Zone", "priority": "SLAM"},
    {"player": "Jonathan Taylor", "stat": "Rush Attempts", "line": 18.5, "proj": 23.5, 
     "edge": 5.0, "edge_pct": 26.8, "hit_rate": 73, "value": 100, "play": "OVER ✅", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "JAX #28 Rush D", "priority": "SLAM"},
    {"player": "Jaylen Warren", "stat": "Rush Yards", "line": 30.5, "proj": 38.6, 
     "edge": 8.1, "edge_pct": 26.7, "hit_rate": 79, "value": 100, "play": "OVER ✅", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "CLE #20 Rush D", "priority": "SLAM"},
    {"player": "Jameis Winston", "stat": "INTs", "line": 0.5, "proj": 1.6, 
     "edge": 1.1, "edge_pct": 222.0, "hit_rate": 88, "value": 100, "play": "OVER ✅", 
     "trend": "🔥", "cons": "⚡", "opp": "PIT #5 Pass D", "priority": "SLAM"},
    
    # SLAM UNDERS
    {"player": "Travis Etienne", "stat": "Rush Yards", "line": 67.5, "proj": 37.5, 
     "edge": -30.0, "edge_pct": -44.4, "hit_rate": 0, "value": 0, "play": "UNDER ✅", 
     "trend": "📉", "cons": "🔒🔒🔒", "opp": "IND #18 Rush D", "priority": "SLAM", 
     "risk": "Bigsby now lead back"},
    {"player": "Travis Etienne", "stat": "Rush+Rec Yds", "line": 85.5, "proj": 48.1, 
     "edge": -37.4, "edge_pct": -43.7, "hit_rate": 0, "value": 0, "play": "UNDER ✅", 
     "trend": "📉", "cons": "🔒🔒🔒", "opp": "IND", "priority": "SLAM", 
     "risk": "Reduced role"},
    {"player": "Nick Chubb", "stat": "Rush Yards", "line": 45.5, "proj": 29.3, 
     "edge": -16.2, "edge_pct": -35.6, "hit_rate": 0, "value": 0, "play": "UNDER ✅", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "PIT #3 Rush D", "priority": "SLAM", 
     "risk": "Post-injury + elite D"},
    {"player": "Trevor Lawrence", "stat": "Pass TDs", "line": 1.5, "proj": 1.0, 
     "edge": -0.5, "edge_pct": -31.5, "hit_rate": 20, "value": 0, "play": "UNDER ✅", 
     "trend": "➡️", "cons": "⚡", "opp": "IND #15 Red Zone D", "priority": "SLAM", 
     "risk": "Shoulder questionable"},
    
    # STRONG PLAYS
    {"player": "Myles Garrett", "stat": "Sacks", "line": 0.5, "proj": 1.0, 
     "edge": 0.5, "edge_pct": 100.1, "hit_rate": 64, "value": 100, "play": "OVER", 
     "trend": "📈", "cons": "⚡", "opp": "PIT 28 sacks allowed", "priority": "STRONG"},
    {"player": "Brian Thomas", "stat": "Rec Yards", "line": 65.5, "proj": 77.2, 
     "edge": 11.7, "edge_pct": 17.8, "hit_rate": 94, "value": 100, "play": "OVER", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "IND #12 Pass D", "priority": "STRONG"},
    {"player": "Joe Flacco", "stat": "Pass Yards", "line": 215.5, "proj": 246.3, 
     "edge": 30.8, "edge_pct": 14.3, "hit_rate": 60, "value": 100, "play": "OVER", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "JAX #26 Pass D", "priority": "STRONG"},
    {"player": "Pat Freiermuth", "stat": "Rec Yards", "line": 30.5, "proj": 35.7, 
     "edge": 5.2, "edge_pct": 17.1, "hit_rate": 80, "value": 100, "play": "OVER", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "CLE #15 Pass D", "priority": "STRONG"},
    
    # LEAN PLAYS
    {"player": "Najee Harris", "stat": "Rush Yards", "line": 55.5, "proj": 61.6, 
     "edge": 6.1, "edge_pct": 10.9, "hit_rate": 67, "value": 91, "play": "LEAN OVER", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "CLE #20 Rush D", "priority": "LEAN"},
    {"player": "George Pickens", "stat": "Rec Yards", "line": 60.5, "proj": 71.0, 
     "edge": 10.5, "edge_pct": 17.3, "hit_rate": 79, "value": 87, "play": "OVER", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "CLE #15 Pass D", "priority": "LEAN"},
    {"player": "Tank Bigsby", "stat": "Rush Yards", "line": 55.5, "proj": 63.4, 
     "edge": 7.9, "edge_pct": 14.2, "hit_rate": 50, "value": 86, "play": "LEAN OVER", 
     "trend": "🔥", "cons": "🔒🔒🔒", "opp": "IND #18 Rush D", "priority": "LEAN"},
    {"player": "T.J. Watt", "stat": "Sacks", "line": 0.5, "proj": 0.7, 
     "edge": 0.2, "edge_pct": 40.0, "hit_rate": 50, "value": 78, "play": "LEAN OVER", 
     "trend": "➡️", "cons": "⚡", "opp": "CLE 42 sacks allowed", "priority": "LEAN"},
    
    # HOLDS/SKIPS
    {"player": "Russell Wilson", "stat": "Pass Yards", "line": 215.5, "proj": 211.8, 
     "edge": -3.7, "edge_pct": -1.7, "hit_rate": 50, "value": 50, "play": "HOLD", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "CLE #15 Pass D", "priority": "SKIP"},
    {"player": "Quinshon Judkins", "stat": "Rush Yards", "line": 55.5, "proj": 46.5, 
     "edge": -9.0, "edge_pct": -16.2, "hit_rate": 31, "value": 0, "play": "UNDER", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "PIT #3 Rush D", "priority": "LEAN"},
    {"player": "Trevor Lawrence", "stat": "Pass Yards", "line": 246.5, "proj": 198.8, 
     "edge": -47.7, "edge_pct": -19.4, "hit_rate": 0, "value": 0, "play": "UNDER", 
     "trend": "➡️", "cons": "🔒🔒🔒", "opp": "IND #12 Pass D", "priority": "LEAN", 
     "risk": "Shoulder questionable"},
]

CORRELATION_GROUPS = [
    {"name": "Pittsburgh Passing Attack", 
     "players": ["George Pickens", "Pat Freiermuth"],
     "risk": "All depend on Wilson having time to throw"},
    {"name": "Jacksonville Rush Committee", 
     "players": ["Travis Etienne", "Tank Bigsby"],
     "risk": "Zero-sum - Bigsby taking Etienne's work"},
    {"name": "PIT Defense vs CLE Pressure", 
     "players": ["T.J. Watt", "Jameis Winston"],
     "risk": "Watt sacks correlate with Winston INTs"},
]


def create_title_page(fig):
    """Create enhanced title page"""
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(5, 8.5, "🏈 UNDERDOG FANTASY", fontsize=28, fontweight='bold', 
            ha='center', color='#1a5276')
    ax.text(5, 7.8, "ANALYSIS SYSTEM v2.0", fontsize=24, fontweight='bold', 
            ha='center', color='#2874a6')
    ax.text(5, 7.2, "Strategic Intelligence Upgrade", fontsize=16, 
            ha='center', color='#5499c7', style='italic')
    
    # Games
    ax.add_patch(FancyBboxPatch((1.5, 5.8), 7, 1.2, boxstyle="round,pad=0.05",
                                 facecolor='#f8f9fa', edgecolor='#2874a6', linewidth=2))
    ax.text(5, 6.4, "SUNDAY DECEMBER 28, 2025", fontsize=14, fontweight='bold', ha='center')
    ax.text(5, 5.95, "PIT @ CLE  •  JAX @ IND", fontsize=18, fontweight='bold', 
            ha='center', color='#1a5276')
    
    # Features box
    features = [
        "📊 Recency Weighting: 40% Season + 60% Last 4 Games",
        "🎯 Matchup Adjustments: Opponent Defense Rankings",
        "📈 Volatility Scoring: Hit Rate + Standard Deviation",
        "🔗 Correlation Detection: Interdependent Pick Warnings",
        "💎 Value Score Algorithm: Multi-Factor Prioritization"
    ]
    
    y_pos = 5.2
    for feature in features:
        ax.text(5, y_pos, feature, fontsize=11, ha='center', color='#2c3e50')
        y_pos -= 0.4
    
    # Stats summary
    slam_overs = len([p for p in ANALYZED_PICKS if p["priority"] == "SLAM" and "OVER" in p["play"]])
    slam_unders = len([p for p in ANALYZED_PICKS if p["priority"] == "SLAM" and "UNDER" in p["play"]])
    strong = len([p for p in ANALYZED_PICKS if p["priority"] == "STRONG"])
    lean = len([p for p in ANALYZED_PICKS if p["priority"] == "LEAN"])
    
    ax.add_patch(Rectangle((1, 1.5), 8, 1.5, facecolor='#e8f6f3', edgecolor='#1abc9c', linewidth=2))
    ax.text(5, 2.6, "ANALYSIS SUMMARY", fontsize=12, fontweight='bold', ha='center')
    ax.text(5, 2.1, f"SLAM OVERS: {slam_overs}  •  SLAM UNDERS: {slam_unders}  •  STRONG: {strong}  •  LEAN: {lean}", 
            fontsize=11, ha='center', color='#1a5276')
    
    ax.text(5, 0.5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 
            fontsize=9, ha='center', color='#7f8c8d')


def create_priority_plays_page(fig):
    """Create top priority plays page"""
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    ax.text(5, 9.5, "🏆 TOP PRIORITY PLAYS", fontsize=20, fontweight='bold', ha='center', color='#1a5276')
    ax.text(5, 9.1, "Highest Value Score | Best Edge + Consistency", fontsize=11, ha='center', color='#5499c7')
    
    # Get top plays
    top_plays = [p for p in ANALYZED_PICKS if p["value"] >= 90 and p["priority"] in ["SLAM", "STRONG"]][:8]
    
    y_pos = 8.5
    for i, pick in enumerate(top_plays, 1):
        direction = "OVER" if "OVER" in pick["play"] else "UNDER"
        color = '#27ae60' if "OVER" in pick["play"] else '#e74c3c'
        
        # Box for each pick
        ax.add_patch(FancyBboxPatch((0.3, y_pos-0.8), 9.4, 0.9, boxstyle="round,pad=0.02",
                                     facecolor='#f8f9fa', edgecolor=color, linewidth=2))
        
        # Priority number
        ax.text(0.6, y_pos-0.35, f"#{i}", fontsize=14, fontweight='bold', color=color)
        
        # Player and stat
        ax.text(1.2, y_pos-0.25, f"{pick['player']}", fontsize=12, fontweight='bold', color='#2c3e50')
        ax.text(1.2, y_pos-0.55, f"{pick['stat']} {direction} {pick['line']}", fontsize=10, color='#5d6d7e')
        
        # Projection
        ax.text(5.5, y_pos-0.25, f"Proj: {pick['proj']:.1f}", fontsize=10, color='#2c3e50')
        ax.text(5.5, y_pos-0.55, f"Edge: {pick['edge']:+.1f} ({pick['edge_pct']:+.1f}%)", fontsize=9, color=color)
        
        # Hit rate and value
        ax.text(7.5, y_pos-0.25, f"Hit: {pick['hit_rate']:.0f}%", fontsize=10, color='#2c3e50')
        ax.text(7.5, y_pos-0.55, f"Value: {pick['value']:.0f}", fontsize=10, fontweight='bold', color=color)
        
        # Matchup
        ax.text(9.5, y_pos-0.35, pick.get('opp', '')[:12], fontsize=8, ha='right', color='#7f8c8d')
        
        y_pos -= 1.0
    
    # Legend at bottom
    ax.text(5, 0.5, "Value Score: Edge × HitRate × Consistency × Matchup", fontsize=9, ha='center', color='#7f8c8d')


def create_slam_plays_page(fig):
    """Create slam plays summary page"""
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    ax.text(5, 9.5, "🎯 SLAM PLAYS", fontsize=20, fontweight='bold', ha='center', color='#1a5276')
    ax.text(5, 9.1, "Highest Confidence Picks", fontsize=11, ha='center', color='#5499c7')
    
    # SLAM OVERS
    slam_overs = [p for p in ANALYZED_PICKS if p["priority"] == "SLAM" and "OVER" in p["play"]]
    
    ax.add_patch(Rectangle((0.3, 5.5), 9.4, 3.3, facecolor='#e8f8f5', edgecolor='#27ae60', linewidth=2))
    ax.text(5, 8.5, "✅ SLAM OVERS", fontsize=14, fontweight='bold', ha='center', color='#27ae60')
    
    y_pos = 8.0
    for pick in slam_overs:
        ax.text(0.7, y_pos, f"• {pick['player']} {pick['stat']} OVER {pick['line']}", 
                fontsize=10, color='#1e8449')
        ax.text(7.5, y_pos, f"Proj: {pick['proj']:.1f} | Hit: {pick['hit_rate']:.0f}%", 
                fontsize=9, color='#27ae60')
        y_pos -= 0.4
    
    # SLAM UNDERS
    slam_unders = [p for p in ANALYZED_PICKS if p["priority"] == "SLAM" and "UNDER" in p["play"]]
    
    ax.add_patch(Rectangle((0.3, 1.5), 9.4, 3.5, facecolor='#fdedec', edgecolor='#e74c3c', linewidth=2))
    ax.text(5, 4.7, "❌ SLAM UNDERS", fontsize=14, fontweight='bold', ha='center', color='#e74c3c')
    
    y_pos = 4.3
    for pick in slam_unders:
        risk_text = f" ⚠️ {pick.get('risk', '')}" if pick.get('risk') else ""
        ax.text(0.7, y_pos, f"• {pick['player']} {pick['stat']} UNDER {pick['line']}", 
                fontsize=10, color='#922b21')
        ax.text(7.5, y_pos, f"Proj: {pick['proj']:.1f} | Hit: {pick['hit_rate']:.0f}%", 
                fontsize=9, color='#e74c3c')
        if risk_text:
            y_pos -= 0.35
            ax.text(0.9, y_pos, risk_text, fontsize=8, color='#c0392b', style='italic')
        y_pos -= 0.45
    
    ax.text(5, 0.8, "MAX PLAY (3-4 units) on all SLAM plays", fontsize=10, 
            fontweight='bold', ha='center', color='#1a5276')


def create_value_chart_page(fig):
    """Create value score visualization"""
    ax = fig.add_subplot(111)
    
    # Get plays with value > 0
    plays_with_value = [p for p in ANALYZED_PICKS if p["value"] > 0]
    plays_sorted = sorted(plays_with_value, key=lambda x: x["value"], reverse=True)[:12]
    
    players = [f"{p['player'][:10]} {p['stat'][:8]}" for p in plays_sorted]
    values = [p["value"] for p in plays_sorted]
    colors = ['#27ae60' if "OVER" in p["play"] else '#e74c3c' for p in plays_sorted]
    
    y_pos = range(len(players))
    bars = ax.barh(y_pos, values, color=colors, edgecolor='white', linewidth=1)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(players, fontsize=9)
    ax.set_xlabel("Value Score", fontsize=10)
    ax.set_title("📊 VALUE SCORE RANKINGS\n(Higher = Better Risk-Adjusted Value)", fontsize=14, fontweight='bold')
    
    # Add value labels
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, 
                f'{val:.0f}', va='center', fontsize=9)
    
    ax.set_xlim(0, 115)
    ax.invert_yaxis()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Legend
    ax.plot([], [], 's', color='#27ae60', markersize=10, label='OVER')
    ax.plot([], [], 's', color='#e74c3c', markersize=10, label='UNDER')
    ax.legend(loc='lower right')


def create_correlation_page(fig):
    """Create correlation warnings page"""
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    ax.text(5, 9.5, "🔗 CORRELATION WARNINGS", fontsize=20, fontweight='bold', ha='center', color='#c0392b')
    ax.text(5, 9.0, "Avoid stacking correlated picks in same entry", fontsize=11, ha='center', color='#e74c3c')
    
    y_pos = 8.2
    for group in CORRELATION_GROUPS:
        ax.add_patch(FancyBboxPatch((0.5, y_pos-1.5), 9, 1.6, boxstyle="round,pad=0.05",
                                     facecolor='#fef5e7', edgecolor='#f39c12', linewidth=2))
        
        ax.text(5, y_pos-0.3, f"⚠️ {group['name']}", fontsize=12, fontweight='bold', 
                ha='center', color='#d68910')
        
        players_text = " • ".join(group['players'])
        ax.text(5, y_pos-0.7, players_text, fontsize=10, ha='center', color='#7e5109')
        ax.text(5, y_pos-1.1, group['risk'], fontsize=9, ha='center', color='#935116', style='italic')
        
        y_pos -= 2.0
    
    # Recommendation box
    ax.add_patch(Rectangle((1, 0.8), 8, 1.2, facecolor='#e8f8f5', edgecolor='#1abc9c', linewidth=2))
    ax.text(5, 1.6, "💡 RECOMMENDATION", fontsize=11, fontweight='bold', ha='center', color='#16a085')
    ax.text(5, 1.15, "Select 1-2 max from each correlated group", fontsize=10, ha='center', color='#148f77')


def create_matchup_context_page(fig):
    """Create matchup context page"""
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    ax.text(5, 9.5, "MATCHUP CONTEXT", fontsize=20, fontweight='bold', ha='center', color='#1a5276')
    
    # PIT @ CLE
    rect1 = Rectangle((0.3, 5.2), 4.5, 4)
    rect1.set_facecolor('#fef9e7')
    rect1.set_edgecolor('#f1c40f')
    rect1.set_linewidth(2)
    ax.add_patch(rect1)
    ax.text(2.55, 8.9, "PIT @ CLE", fontsize=14, fontweight='bold', ha='center', color='#b7950b')
    
    pit_cle_context = [
        "PIT Defense: #5 Overall, #3 Rush D",
        "CLE O-Line: 42 sacks allowed (4th most)",
        "→ Winston under pressure = INTs",
        "→ Chubb struggles vs elite front",
        "",
        "CLE Defense: #18 Overall, #20 Rush D",
        "PIT Game Script: Run-heavy favorites",
        "→ Warren/Harris both viable",
        "→ Limited passing game upside"
    ]
    
    y = 8.4
    for line in pit_cle_context:
        ax.text(0.6, y, line, fontsize=9, color='#7e5109')
        y -= 0.35
    
    # JAX @ IND
    ax.add_patch(Rectangle((5.2, 5.2), 4.5, 4), facecolor='#e8f6f3', edgecolor='#1abc9c', linewidth=2)
    ax.text(7.45, 8.9, "JAX @ IND", fontsize=14, fontweight='bold', ha='center', color='#148f77')
    
    jax_ind_context = [
        "JAX Defense: #28 Rush D (worst tier)",
        "IND home favorites (-3.5)",
        "→ Jonathan Taylor smash spot",
        "→ Heavy rushing, TD upside",
        "",
        "IND Defense: #12 Pass D, #15 Red Zone",
        "Lawrence shoulder questionable",
        "→ Etienne reduced role (Bigsby)",
        "→ Brian Thomas still productive"
    ]
    
    y = 8.4
    for line in jax_ind_context:
        ax.text(5.5, y, line, fontsize=9, color='#117864')
        y -= 0.35
    
    # Key takeaways
    ax.add_patch(Rectangle((0.3, 0.8), 9.4, 4.0), facecolor='#f4f6f7', edgecolor='#5d6d7e', linewidth=2)
    ax.text(5, 4.5, "🔑 KEY TAKEAWAYS", fontsize=12, fontweight='bold', ha='center', color='#2c3e50')
    
    takeaways = [
        "1. Jonathan Taylor OVER 70.5 Rush Yards is LOCK OF THE DAY (100% hit rate)",
        "2. Jameis Winston OVER 0.5 INTs vs PIT #5 defense (88% hit rate, 🔥 trend)",
        "3. Travis Etienne UNDER all props - Bigsby taking over as lead back",
        "4. Nick Chubb UNDER 45.5 - Post-injury + PIT #3 Rush D = disaster",
        "5. Myles Garrett sacks profitable - PIT O-Line allows pressure"
    ]
    
    y = 4.0
    for t in takeaways:
        ax.text(0.6, y, t, fontsize=9, color='#2c3e50')
        y -= 0.6


def create_cheatsheet_page(fig):
    """Create quick reference cheatsheet"""
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    ax.text(5, 9.5, "📋 GAME DAY CHEATSHEET", fontsize=20, fontweight='bold', ha='center', color='#1a5276')
    ax.text(5, 9.0, "Quick Reference - Print This Page", fontsize=11, ha='center', color='#5499c7')
    
    # MAX PLAYS
    ax.add_patch(Rectangle((0.3, 6.5), 4.5, 2.2), facecolor='#d5f5e3', edgecolor='#27ae60', linewidth=2)
    ax.text(2.55, 8.4, "💎 MAX PLAYS (3-4 units)", fontsize=11, fontweight='bold', ha='center', color='#1e8449')
    
    max_plays = [
        "JT Rush Yds OVER 70.5",
        "JT TDs OVER 0.5",
        "Warren Rush OVER 30.5",
        "Winston INTs OVER 0.5"
    ]
    y = 7.9
    for p in max_plays:
        ax.text(0.6, y, f"✓ {p}", fontsize=9, color='#1e8449')
        y -= 0.35
    
    # STRONG PLAYS
    ax.add_patch(Rectangle((5.2, 6.5), 4.5, 2.2), facecolor='#d4efdf', edgecolor='#2ecc71', linewidth=2)
    ax.text(7.45, 8.4, "💪 STRONG (2-3 units)", fontsize=11, fontweight='bold', ha='center', color='#239b56')
    
    strong_plays = [
        "Brian Thomas OVER 65.5",
        "Flacco Pass Yds OVER 215.5",
        "Freiermuth OVER 30.5",
        "Garrett Sacks OVER 0.5"
    ]
    y = 7.9
    for p in strong_plays:
        ax.text(5.5, y, f"✓ {p}", fontsize=9, color='#239b56')
        y -= 0.35
    
    # SLAM UNDERS
    ax.add_patch(Rectangle((0.3, 4.0), 4.5, 2.2), facecolor='#fadbd8', edgecolor='#e74c3c', linewidth=2)
    ax.text(2.55, 5.9, "🔻 SLAM UNDERS", fontsize=11, fontweight='bold', ha='center', color='#922b21')
    
    unders = [
        "Etienne Rush UNDER 67.5",
        "Etienne R+R UNDER 85.5",
        "Chubb Rush UNDER 45.5",
        "Lawrence TDs UNDER 1.5"
    ]
    y = 5.4
    for p in unders:
        ax.text(0.6, y, f"✗ {p}", fontsize=9, color='#922b21')
        y -= 0.35
    
    # AVOID/HOLDS
    ax.add_patch(Rectangle((5.2, 4.0), 4.5, 2.2), facecolor='#f4f6f7', edgecolor='#7f8c8d', linewidth=2)
    ax.text(7.45, 5.9, "⏸️ HOLD / AVOID", fontsize=11, fontweight='bold', ha='center', color='#5d6d7e')
    
    avoids = [
        "Wilson Pass Yards (line fair)",
        "Winston Pass Yards (volatile)",
        "Pickens Receptions (line fair)",
        "Lawrence Pass Yards (injury)"
    ]
    y = 5.4
    for p in avoids:
        ax.text(5.5, y, f"- {p}", fontsize=9, color='#5d6d7e')
        y -= 0.35
    
    # Correlation reminder
    ax.add_patch(Rectangle((0.3, 1.5), 9.4, 2.2), facecolor='#fef5e7', edgecolor='#f39c12', linewidth=2)
    ax.text(5, 3.4, "⚠️ CORRELATION REMINDER", fontsize=11, fontweight='bold', ha='center', color='#d68910')
    ax.text(5, 2.9, "• PIT Pass Attack: Pick 1-2 of Pickens/Freiermuth", fontsize=9, ha='center', color='#7e5109')
    ax.text(5, 2.5, "• JAX Backfield: Etienne UNDER + Bigsby OVER = same thesis", fontsize=9, ha='center', color='#7e5109')
    ax.text(5, 2.1, "• Watt sacks ↔ Winston INTs (good stack)", fontsize=9, ha='center', color='#7e5109')
    
    ax.text(5, 0.7, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Good luck! 🍀", 
            fontsize=9, ha='center', color='#7f8c8d')


def generate_pdf():
    """Generate the complete PDF report"""
    pdf_path = "outputs/analysis_v2_report.pdf"
    
    with PdfPages(pdf_path) as pdf:
        # Page 1: Title
        fig = plt.figure(figsize=(11, 8.5))
        create_title_page(fig)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 2: Priority Plays
        fig = plt.figure(figsize=(11, 8.5))
        create_priority_plays_page(fig)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 3: Slam Plays
        fig = plt.figure(figsize=(11, 8.5))
        create_slam_plays_page(fig)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 4: Value Chart
        fig = plt.figure(figsize=(11, 8.5))
        create_value_chart_page(fig)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 5: Correlation Warnings
        fig = plt.figure(figsize=(11, 8.5))
        create_correlation_page(fig)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 6: Matchup Context
        fig = plt.figure(figsize=(11, 8.5))
        create_matchup_context_page(fig)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 7: Cheatsheet
        fig = plt.figure(figsize=(11, 8.5))
        create_cheatsheet_page(fig)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
    
    print(f"✅ PDF Report Generated: {pdf_path}")
    print(f"   Total Pages: 7")
    return pdf_path


if __name__ == "__main__":
    generate_pdf()
