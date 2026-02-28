"""
SDG Interactive Tester
======================
Test the Stat Deviation Gate with your own values.

Usage:
    python tools/test_sdg.py
"""

from core.stat_deviation_gate import stat_deviation_gate, SDG_CONFIG

def main():
    print("\n" + "="*60)
    print("🎯 STAT DEVIATION GATE — Interactive Tester")
    print("="*60)
    print("\nSDG blocks coin-flip bets where line ≈ player mean")
    print("Formula: z_stat = (line - μ) / σ")
    print(f"\nThresholds: |z| < 0.25 = HEAVY (×0.70), |z| < 0.50 = MEDIUM (×0.85)")
    
    while True:
        print("\n" + "-"*40)
        try:
            line = float(input("Enter LINE (e.g., 25.5): "))
            mu = float(input("Enter player MEAN (μ): "))
            sigma = float(input("Enter player STD DEV (σ): "))
            stat = input("Enter STAT (pts/reb/ast/3pm/pra) [pts]: ").strip() or "pts"
            
            mult, desc, details = stat_deviation_gate(mu, sigma, line, stat)
            
            print(f"\n📊 RESULT:")
            print(f"   z_stat = ({line} - {mu}) / {sigma} = {details['z_stat']:+.3f}")
            print(f"   {desc}")
            print(f"   Multiplier: {mult:.2f}")
            
            # Show impact on example probability
            example_prob = 65.0
            adjusted = example_prob * mult
            print(f"\n   Example: {example_prob}% → {adjusted:.1f}% (after SDG)")
            if adjusted < 55:
                print("   ⚠️  Would be REJECTED (below 55%)")
            
        except ValueError:
            print("Invalid input, try again")
        except KeyboardInterrupt:
            print("\n\nBye!")
            break

if __name__ == "__main__":
    main()
