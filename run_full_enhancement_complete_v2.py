# -*- coding: utf-8 -*-
"""
FULL 4-LAYER ENHANCEMENT - COMPLETE SLATE
Apply empirical -> Bayesian -> Rest Day -> Matchup adjustments with analytical insights
"""

import json
from pathlib import Path

# Matchup-specific adjustments from comprehensive analysis
MATCHUP_ADJUSTMENTS = {
    # IND@CHA Game
    ("LaMelo Ball", "assists"): {"adj": 0.10, "reason": "Carlisle drop coverage allows 7.8 AST/game to PGs"},
    ("LaMelo Ball", "points"): {"adj": 0.05, "reason": "CHA pace + volume boost (102.0 projected)"},
    ("Pascal Siakam", "points"): {"adj": 0.08, "reason": "CHA gives up 21.5 ppg to PFs, mismatch"},
    ("Andrew Nembhard", "points"): {"adj": 0.05, "reason": "CHA allows 52.1% in paint, P&R dominance"},
    ("Brandon Miller", "3pm"): {"adj": 0.05, "reason": "IND allows 36.2% from 3, spot-up chances"},
    ("Miles Bridges", "points"): {"adj": 0.03, "reason": "IND solid defense but CHA pace helps"},
    
    # CLE@MIN Game
    ("Anthony Edwards", "points"): {"adj": 0.07, "reason": "Hunts switches, CLE allows 37.1% on perimeter"},
    ("Anthony Edwards", "3pm"): {"adj": 0.05, "reason": "Perimeter switches vulnerable"},
    ("Donovan Mitchell", "points"): {"adj": 0.06, "reason": "P&R mastery vs Gobert drop coverage"},
    ("Darius Garland", "assists"): {"adj": -0.05, "reason": "B2B fatigue (-10%) offset by matchup (+5%)"},
    ("Darius Garland", "points"): {"adj": -0.08, "reason": "B2B: CLE 106 OFF_RTG vs 118.9 normal"},
    ("Julius Randle", "rebounds"): {"adj": 0.08, "reason": "CLE frontcourt out of position on B2B"},
    ("Julius Randle", "pra"): {"adj": 0.06, "reason": "Versatile big vs CLE B2B fatigue"},
    ("Evan Mobley", "points"): {"adj": -0.08, "reason": "B2B struggles, 106 OFF_RTG expected"},
    ("Jarrett Allen", "rebounds"): {"adj": -0.05, "reason": "B2B fatigue limits energy"},
    
    # MIA@CHI Game
    ("Bam Adebayo", "points"): {"adj": 0.10, "reason": "CHI allows 58.2% at rim, no rim protection"},
    ("Bam Adebayo", "rebounds"): {"adj": 0.07, "reason": "CHI weak interior, Bam feast"},
    ("Tyler Herro", "points"): {"adj": 0.06, "reason": "Isolation vs CHI poor perimeter defense"},
    ("Nikola Vucevic", "points"): {"adj": 0.05, "reason": "0.98 PPP on post-ups vs MIA"},
    ("Coby White", "points"): {"adj": 0.04, "reason": "Transition if CHI pushes vs MIA zone"},
    ("Norman Powell", "points"): {"adj": 0.03, "reason": "MIA ball movement limited by CHI"},
    
    # DAL@UTA Game (BLOWOUT RISK)
    ("Anthony Davis", "points"): {"adj": 0.02, "reason": "+12% matchup (UTA 29th DEF) but -10% B2B"},
    ("Anthony Davis", "rebounds"): {"adj": 0.02, "reason": "UTA weak but B2B fatigue"},
    ("Anthony Davis", "pra"): {"adj": -0.03, "reason": "B2B drops AD 3.8 ppg + blowout risk"},
    ("Cooper Flagg", "pra"): {"adj": 0.10, "reason": "Rookie vs rookie, experience edge"},
    ("Klay Thompson", "points"): {"adj": -0.05, "reason": "Blowout risk, minutes concern"},
}

# Blowout risk reductions
BLOWOUT_GAMES = {
    "DAL@UTA": -0.05,  # 22% blowout probability
    "IND@CHA": -0.02,  # 15% blowout probability
}

def apply_bayesian(empirical_prob, prior_alpha=3, prior_beta=3):
    """
    Apply Bayesian Beta-Binomial update
    Prior: Beta(3, 3) - mildly skeptical of extremes
    """
    n_trials = 10  # game sample
    hits = round(empirical_prob * n_trials)
    
    posterior_alpha = prior_alpha + hits
    posterior_beta = prior_beta + (n_trials - hits)
    
    # Expected value of Beta distribution
    bayesian_prob = posterior_alpha / (posterior_alpha + posterior_beta)
    
    return round(bayesian_prob, 4)

def apply_matchup_adjustment(player, stat, base_prob):
    """Apply matchup-specific adjustment from comprehensive analysis"""
    key = (player, stat)
    if key in MATCHUP_ADJUSTMENTS:
        adj = MATCHUP_ADJUSTMENTS[key]["adj"]
        reason = MATCHUP_ADJUSTMENTS[key]["reason"]
        adjusted = min(0.999, max(0.001, base_prob * (1 + adj)))
        return adjusted, reason
    return base_prob, None

def apply_blowout_reduction(game, base_prob):
    """Reduce probability for blowout risk games"""
    if game in BLOWOUT_GAMES:
        reduction = BLOWOUT_GAMES[game]
        adjusted = base_prob * (1 + reduction)
        return adjusted, f"Blowout risk {reduction*100:+.0f}%"
    return base_prob, None

def main():
    print("\n" + "="*80)
    print("FULL 4-LAYER ENHANCEMENT - COMPLETE SLATE")
    print("="*80 + "\n")
    
    # Load hydrated data
    hydrated_file = Path("outputs/jan8_complete_hydrated.json")
    if not hydrated_file.exists():
        print("ERROR: Hydrated data file not found!")
        return
    
    with open(hydrated_file) as f:
        data = json.load(f)
    
    enhanced_picks = []
    qualified_picks = []
    
    print("ENHANCEMENT PIPELINE\n")
    
    for pick in data["picks"]:
        player = pick["player"]
        stat = pick["stat"]
        line = pick["line"]
        opponent = pick["opponent"]
        team = pick["team"]
        
        # Derive game matchup
        game_matchups = {
            ("IND", "CHA"): "IND@CHA",
            ("CHA", "IND"): "IND@CHA",
            ("CLE", "MIN"): "CLE@MIN",
            ("MIN", "CLE"): "CLE@MIN",
            ("MIA", "CHI"): "MIA@CHI",
            ("CHI", "MIA"): "MIA@CHI",
            ("DAL", "UTA"): "DAL@UTA",
            ("UTA", "DAL"): "DAL@UTA",
        }
        game = game_matchups.get((team, opponent), f"{team}@{opponent}")
        
        # LAYER 1: Empirical probability
        empirical = pick["empirical_prob"]
        
        # LAYER 2: Bayesian update
        bayesian = apply_bayesian(empirical)
        
        # LAYER 3: Matchup adjustment
        matchup_adj, matchup_reason = apply_matchup_adjustment(player, stat, bayesian)
        
        # LAYER 4: Blowout reduction
        final_prob, blowout_note = apply_blowout_reduction(game, matchup_adj)
        
        # Round final probability
        final_prob = round(final_prob, 4)
        
        # Build enhancement detail
        enhancement_detail = {
            "empirical": empirical,
            "bayesian": bayesian,
            "matchup_adj": matchup_adj if matchup_reason else None,
            "matchup_reason": matchup_reason,
            "blowout_adj": blowout_note,
            "final_prob": final_prob
        }
        
        enhanced_pick = {
            **pick,
            "game": game,
            **enhancement_detail,
            "qualified": final_prob >= 0.65
        }
        
        enhanced_picks.append(enhanced_pick)
        
        # Track qualified picks
        if enhanced_pick["qualified"]:
            qualified_picks.append(enhanced_pick)
            status = "QUALIFIED"
        else:
            status = "DQ"
        
        # Print progress
        prob_change = f"{empirical:.0%} -> {final_prob:.0%}"
        print(f"{status:10} {player:20} {stat:10} {line:5}+ [{prob_change}]")
        if matchup_reason:
            print(f"           {matchup_reason}")
    
    # Save enhanced data
    output = {
        "date": data["date"],
        "games": data["games"],
        "picks": enhanced_picks,
        "qualified_count": len(qualified_picks)
    }
    
    output_path = Path("outputs/jan8_complete_enhanced.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"ENHANCEMENT COMPLETE!")
    print(f"Total picks processed: {len(enhanced_picks)}")
    print(f"Qualified picks (>=65%): {len(qualified_picks)}")
    print(f"Saved to: {output_path}")
    
    # Show qualified picks by game
    print(f"\n{'='*80}")
    print("QUALIFIED PICKS BY GAME\n")
    
    games_breakdown = {}
    for pick in qualified_picks:
        game = pick["game"]
        if game not in games_breakdown:
            games_breakdown[game] = []
        games_breakdown[game].append(pick)
    
    for game, picks in sorted(games_breakdown.items()):
        print(f"\n{game} ({len(picks)} qualified)")
        for pick in sorted(picks, key=lambda x: -x["final_prob"]):
            print(f"   {pick['player']:20} {pick['stat']:10} {pick['line']:5}+ [{pick['final_prob']:.0%}]")
            if pick['matchup_reason']:
                print(f"      -> {pick['matchup_reason']}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
