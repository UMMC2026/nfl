"""
4-TEAM PDF REPORT GENERATOR
============================
Generates visual PDF with analysis for all 4 teams:
- Pittsburgh Steelers
- Cleveland Browns  
- Jacksonville Jaguars
- Indianapolis Colts
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from datetime import datetime
import os

# Create outputs directory
os.makedirs("outputs", exist_ok=True)

# Team data
TEAM_DATA = {
    "PIT": {
        "name": "Pittsburgh Steelers",
        "record": "10-5",
        "color": "#FFB612",  # Steelers Gold
        "slams": [
            ("T.J. Watt", "Sacks", 0.5, 0.72, "OVER", 95),
            ("George Pickens", "Rec Yards", 60.5, 72.8, "OVER", 91),
            ("Pat Freiermuth", "Rec Yards", 30.5, 36.4, "OVER", 89),
            ("Jaylen Warren", "Rush Yards", 30.5, 35.2, "OVER", 81),
        ],
        "leans": [
            ("Najee Harris", "Rush Yards", 55.5, 61.3, "OVER", 71),
            ("Calvin Austin III", "Rec Yards", 28.5, 32.3, "OVER", 77),
        ]
    },
    "CLE": {
        "name": "Cleveland Browns",
        "record": "3-12",
        "color": "#FF3C00",  # Browns Orange
        "slams": [
            ("Myles Garrett", "Sacks", 0.5, 0.89, "OVER", 95),
            ("Jameis Winston", "INTs", 0.5, 1.25, "OVER", 95),
            ("Nick Chubb", "Rush Yards", 45.5, 35.0, "UNDER", 95),
            ("Jerry Jeudy", "Rec Yards", 45.5, 58.6, "OVER", 95),
            ("David Njoku", "Rec Yards", 35.5, 48.7, "OVER", 95),
            ("Elijah Moore", "Rec Yards", 22.5, 26.1, "OVER", 82),
        ],
        "leans": [
            ("Quinshon Judkins", "Rush Yards", 55.5, 51.7, "UNDER", 64),
            ("Cedric Tillman", "Rec Yards", 35.5, 39.0, "OVER", 70),
        ]
    },
    "JAX": {
        "name": "Jacksonville Jaguars",
        "record": "4-13",
        "color": "#006778",  # Jaguars Teal
        "slams": [
            ("Travis Etienne", "Rush Yards", 67.5, 37.2, "UNDER", 95),
            ("Travis Etienne", "Rush+Rec", 85.5, 54.1, "UNDER", 95),
            ("Trevor Lawrence", "Pass Yards", 246.5, 204.5, "UNDER", 84),
            ("Trevor Lawrence", "Pass TDs", 1.5, 1.1, "UNDER", 95),
            ("Trevor Lawrence", "INTs", 0.5, 0.7, "OVER", 95),
            ("Brian Thomas", "Rec Yards", 65.5, 75.4, "OVER", 80),
            ("Travon Walker", "Sacks", 0.5, 0.62, "OVER", 95),
        ],
        "leans": [
            ("Tank Bigsby", "Rush Yards", 45.5, 47.9, "OVER", 61),
            ("Foyesade Oluokun", "Tackles", 7.5, 8.3, "OVER", 71),
        ]
    },
    "IND": {
        "name": "Indianapolis Colts",
        "record": "8-7",
        "color": "#002C5F",  # Colts Blue
        "slams": [
            ("Jonathan Taylor", "Rush Yards", 70.5, 99.3, "OVER", 95),
            ("Jonathan Taylor", "TDs", 0.5, 1.27, "OVER", 95),
            ("Jonathan Taylor", "Long Rush", 16.5, 20.0, "OVER", 92),
            ("Alec Pierce", "Rec Yards", 50.5, 58.1, "OVER", 80),
        ],
        "leans": [
            ("Michael Pittman", "Rec Yards", 44.5, 50.5, "OVER", 77),
            ("Zaire Franklin", "Tackles", 6.5, 7.2, "OVER", 72),
            ("Joe Flacco", "Pass Yards", 205.5, 220.0, "OVER", 64),
        ]
    }
}


def create_title_page(pdf):
    """Create title page"""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 8.5)
    ax.axis('off')
    
    # Title
    ax.text(5.5, 7, "UNDERDOG FANTASY", fontsize=32, ha='center', 
            fontweight='bold', color='#1a1a2e')
    ax.text(5.5, 6.2, "4-TEAM NFL PROPS ANALYSIS", fontsize=24, ha='center',
            fontweight='bold', color='#4a4a6a')
    
    # Games
    ax.text(5.5, 5, "GAME 1: PIT @ CLE", fontsize=18, ha='center', color='#333')
    ax.text(5.5, 4.5, "GAME 2: JAX @ IND", fontsize=18, ha='center', color='#333')
    
    # Teams grid
    teams = [("PIT", "Pittsburgh Steelers", "10-5", "#FFB612"),
             ("CLE", "Cleveland Browns", "3-12", "#FF3C00"),
             ("JAX", "Jacksonville Jaguars", "4-13", "#006778"),
             ("IND", "Indianapolis Colts", "8-7", "#002C5F")]
    
    for i, (abbr, name, record, color) in enumerate(teams):
        x = 2.5 + (i % 2) * 6
        y = 3 - (i // 2) * 1.2
        ax.add_patch(plt.Rectangle((x-1, y-0.3), 2, 0.8, 
                     facecolor=color, edgecolor='black', alpha=0.8))
        ax.text(x, y, f"{abbr}\n{record}", fontsize=12, ha='center', va='center',
                color='white', fontweight='bold')
    
    # Date
    ax.text(5.5, 0.5, f"Generated: {datetime.now().strftime('%B %d, %Y')}", 
            fontsize=12, ha='center', color='gray')
    ax.text(5.5, 0.2, "Based on 2024 Pro-Football-Reference Stats", 
            fontsize=10, ha='center', color='gray')
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def create_team_page(pdf, team_code, team_data):
    """Create a page for one team"""
    fig = plt.figure(figsize=(11, 8.5))
    
    # Title
    fig.suptitle(f"{team_data['name']} ({team_data['record']})", 
                 fontsize=20, fontweight='bold', y=0.95)
    
    # Create grid
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3, 
                          left=0.1, right=0.9, top=0.85, bottom=0.1)
    
    # SLAM PLAYS bar chart
    ax1 = fig.add_subplot(gs[0, :])
    slams = team_data['slams']
    
    if slams:
        players = [f"{s[0]}\n{s[1]}" for s in slams]
        lines = [s[2] for s in slams]
        avgs = [s[3] for s in slams]
        
        x = np.arange(len(players))
        width = 0.35
        
        bars1 = ax1.bar(x - width/2, lines, width, label='Line', color='lightcoral', alpha=0.8)
        bars2 = ax1.bar(x + width/2, avgs, width, label='Season Avg', color='lightgreen', alpha=0.8)
        
        ax1.set_ylabel('Value')
        ax1.set_title(f'{team_code} SLAM PLAYS - Line vs Season Average', fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(players, fontsize=8)
        ax1.legend()
        
        # Add direction labels
        for i, slam in enumerate(slams):
            direction = slam[4]
            conf = slam[5]
            color = 'green' if direction == 'OVER' else 'red'
            y_pos = max(slam[2], slam[3]) + 2
            ax1.text(i, y_pos, f"{direction}\n{conf}%", ha='center', fontsize=8, 
                    color=color, fontweight='bold')
    else:
        ax1.text(0.5, 0.5, 'No Slam Plays', ha='center', va='center', fontsize=14)
        ax1.axis('off')
    
    # Confidence pie chart
    ax2 = fig.add_subplot(gs[1, 0])
    all_plays = team_data['slams'] + team_data['leans']
    
    if all_plays:
        overs = sum(1 for p in all_plays if p[4] == 'OVER')
        unders = sum(1 for p in all_plays if p[4] == 'UNDER')
        
        if overs + unders > 0:
            ax2.pie([overs, unders], labels=['OVER', 'UNDER'], 
                   colors=['green', 'red'], autopct='%1.0f%%',
                   startangle=90, explode=(0.05, 0.05))
            ax2.set_title('Play Direction Breakdown', fontweight='bold')
    
    # Summary text
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.axis('off')
    
    summary_text = f"{team_code} QUICK PICKS\n\n"
    summary_text += "SLAM PLAYS:\n"
    for slam in team_data['slams'][:4]:
        summary_text += f"  {slam[0]} {slam[4]} {slam[2]} ({slam[1]})\n"
    
    summary_text += "\nLEAN PLAYS:\n"
    for lean in team_data['leans'][:3]:
        summary_text += f"  {lean[0]} {lean[4]} {lean[2]} ({lean[1]})\n"
    
    ax3.text(0.1, 0.9, summary_text, transform=ax3.transAxes, fontsize=10,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def create_combined_top10_page(pdf):
    """Create combined top 10 plays page"""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis('off')
    
    ax.text(0.5, 0.95, "TOP 10 SLAM PLAYS - ALL 4 TEAMS", fontsize=20, 
            ha='center', va='top', fontweight='bold', transform=ax.transAxes)
    
    # Top 10 plays
    top_plays = [
        (1, "Jonathan Taylor", "IND", "Rush Yards", "OVER", 70.5, 99.3, 95),
        (2, "Travis Etienne", "JAX", "Rush Yards", "UNDER", 67.5, 37.2, 95),
        (3, "Nick Chubb", "CLE", "Rush Yards", "UNDER", 45.5, 35.0, 95),
        (4, "T.J. Watt", "PIT", "Sacks", "OVER", 0.5, 0.72, 95),
        (5, "Myles Garrett", "CLE", "Sacks", "OVER", 0.5, 0.89, 95),
        (6, "Jerry Jeudy", "CLE", "Rec Yards", "OVER", 45.5, 58.6, 95),
        (7, "Travis Etienne", "JAX", "Rush+Rec", "UNDER", 85.5, 54.1, 95),
        (8, "George Pickens", "PIT", "Rec Yards", "OVER", 60.5, 72.8, 91),
        (9, "Brian Thomas", "JAX", "Rec Yards", "OVER", 65.5, 75.4, 80),
        (10, "Alec Pierce", "IND", "Rec Yards", "OVER", 50.5, 58.1, 80),
    ]
    
    # Table headers
    headers = ["#", "Player", "Team", "Prop", "Play", "Line", "Avg", "Conf"]
    col_widths = [0.05, 0.22, 0.08, 0.15, 0.1, 0.1, 0.1, 0.1]
    col_x = [0.05]
    for w in col_widths[:-1]:
        col_x.append(col_x[-1] + w)
    
    # Header row
    y_start = 0.85
    for i, (header, x) in enumerate(zip(headers, col_x)):
        ax.text(x, y_start, header, fontsize=11, fontweight='bold', 
                transform=ax.transAxes)
    
    # Draw header line
    ax.plot([0.05, 0.95], [y_start - 0.02, y_start - 0.02], color='black', 
            linewidth=2, transform=ax.transAxes)
    
    # Data rows
    for row_idx, play in enumerate(top_plays):
        y = y_start - 0.06 - (row_idx * 0.07)
        
        rank, player, team, prop, direction, line, avg, conf = play
        row_data = [str(rank), player, team, prop, direction, str(line), f"{avg:.1f}", f"{conf}%"]
        
        # Alternate row colors
        if row_idx % 2 == 0:
            rect = plt.Rectangle((0.05, y - 0.02), 0.9, 0.07, 
                                 facecolor='lightgray', alpha=0.3, 
                                 transform=ax.transAxes, zorder=0)
            ax.add_patch(rect)
        
        for i, (val, x) in enumerate(zip(row_data, col_x)):
            color = 'green' if val == 'OVER' else ('red' if val == 'UNDER' else 'black')
            weight = 'bold' if i == 4 else 'normal'
            ax.text(x, y, val, fontsize=10, color=color, fontweight=weight,
                   transform=ax.transAxes)
    
    # Footer
    ax.text(0.5, 0.1, "Always check injury reports before game time!", 
            fontsize=12, ha='center', style='italic', color='gray',
            transform=ax.transAxes)
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def create_cheatsheet_page(pdf):
    """Create final cheat sheet page"""
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis('off')
    
    ax.text(0.5, 0.95, "SUNDAY QUICK CHEAT SHEET", fontsize=22, 
            ha='center', va='top', fontweight='bold', transform=ax.transAxes,
            color='#1a1a2e')
    
    cheatsheet = """
    GAME 1: PIT @ CLE (Steelers -7.5)
    ----------------------------------------
    PIT:  T.J. Watt OVER 0.5 Sacks | Pickens OVER 60.5 | Freiermuth OVER 30.5
    CLE:  Nick Chubb UNDER 45.5 | Jeudy OVER 45.5 | Njoku OVER 35.5 | Garrett OVER 0.5 Sacks


    GAME 2: JAX @ IND (Colts -3.5)
    ----------------------------------------
    JAX:  Etienne UNDER 67.5 Rush | Etienne UNDER 85.5 R+R | B. Thomas OVER 65.5
    IND:  J. Taylor OVER 70.5 Rush | JT OVER 0.5 TDs | Pierce OVER 50.5


    STRONGEST PLAYS (95% Confidence):
    ----------------------------------------
    1. Jonathan Taylor OVER 70.5 Rush (avg 99.3)
    2. Travis Etienne UNDER 67.5 Rush (avg 37.2)  
    3. Nick Chubb UNDER 45.5 Rush (avg 35.0)
    4. T.J. Watt OVER 0.5 Sacks (avg 0.72)
    5. Myles Garrett OVER 0.5 Sacks (avg 0.89)


    PARLAY IDEAS:
    ----------------------------------------
    Safe 3-Leg:   JT OVER 70.5 + Etienne UNDER 67.5 + Pickens OVER 60.5
    Value 4-Leg:  JT TD + Watt Sack + Garrett Sack + Chubb UNDER 45.5
    """
    
    ax.text(0.08, 0.85, cheatsheet, fontsize=11, va='top', 
            fontfamily='monospace', transform=ax.transAxes,
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    
    ax.text(0.5, 0.05, f"Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", 
            fontsize=10, ha='center', color='gray', transform=ax.transAxes)
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def main():
    """Generate the complete 4-team PDF report"""
    pdf_path = "outputs/4team_props_report.pdf"
    
    print("Generating 4-Team PDF Report...")
    print("=" * 50)
    
    with PdfPages(pdf_path) as pdf:
        # Page 1: Title
        print("  Page 1: Title page...")
        create_title_page(pdf)
        
        # Pages 2-5: Individual team pages
        for i, (team_code, data) in enumerate(TEAM_DATA.items(), 2):
            print(f"  Page {i}: {data['name']}...")
            create_team_page(pdf, team_code, data)
        
        # Page 6: Combined Top 10
        print("  Page 6: Top 10 plays...")
        create_combined_top10_page(pdf)
        
        # Page 7: Cheat Sheet
        print("  Page 7: Cheat sheet...")
        create_cheatsheet_page(pdf)
    
    print("=" * 50)
    print(f"PDF saved to: {pdf_path}")
    print(f"Total pages: 7")
    print("\nPDF Contents:")
    print("  1. Title Page")
    print("  2. Pittsburgh Steelers Analysis")
    print("  3. Cleveland Browns Analysis")
    print("  4. Jacksonville Jaguars Analysis")
    print("  5. Indianapolis Colts Analysis")
    print("  6. Combined Top 10 Plays")
    print("  7. Quick Cheat Sheet")


if __name__ == "__main__":
    main()
