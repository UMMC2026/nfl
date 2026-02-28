"""
REPORT ENHANCER - FUOOM DARK MATTER
Combines templates + reasons + optional LLM polish

Generates subscriber-ready narrative reports
"""

import os
import json
from datetime import datetime
from typing import Optional

from narrative_templates import (
    get_template,
    format_stat_full_name,
    format_direction_verb,
    format_tier_emoji,
    FUOOM_INTRO,
    FUOOM_OUTRO
)
from reason_generator import (
    generate_reasons,
    generate_risks,
    generate_primary_reason,
    format_reasons_as_bullets,
    format_risks_as_bullets
)


def enhance_pick_with_narrative(pick: dict, use_llm: bool = False) -> str:
    """
    Transform a raw pick dict into subscriber-ready narrative
    
    Args:
        pick: Dict with player, stat, line, direction, probability, mu, sigma, etc.
        use_llm: Whether to use Ollama/DeepSeek for additional polish (default: False)
    
    Returns:
        Formatted narrative string for this pick
    """
    # Determine tier from probability
    prob = pick.get('probability', pick.get('final_probability', 0.50))
    if prob >= 0.75:
        tier = 'ELITE'
    elif prob >= 0.65:
        tier = 'STRONG'
    else:
        tier = 'LEAN'
    
    # Prepare data for template
    player = pick.get('player', pick.get('player_name', 'Player'))
    stat = pick.get('stat', pick.get('market', 'stat'))
    line = pick.get('line', 0)
    direction = pick.get('direction', 'higher')
    mu = pick.get('mu', pick.get('mean', 0))
    sigma = pick.get('sigma', pick.get('std', 0))
    
    # Calculate derived values
    gap = mu - line
    buffer_pct = abs(gap) / line * 100 if line > 0 else 0
    recent_hits = pick.get('recent_hits', pick.get('hit_count'))
    recent_total = pick.get('recent_total', 10)
    hit_rate = (recent_hits / recent_total * 100) if recent_hits else None
    
    # Generate reasons and risks
    reasons = generate_reasons(pick)
    risks = generate_risks(pick)
    primary_reason = generate_primary_reason(pick)
    
    # Format values for display
    stat_display = format_stat_full_name(stat)  # e.g., "3-Pointers" 
    direction_verb = format_direction_verb(direction)
    tier_emoji = format_tier_emoji(tier)
    
    # Build narrative using fallback template (more reliable than complex templates)
    narrative = f"""
{tier_emoji} **{tier} PICK**: {player} {direction_verb} {line} {stat_display}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **THE PLAY:**
{player} to {direction_verb} **{line} {stat_display}** vs {pick.get('opponent', 'opponent')}.
{primary_reason}

📊 **THE DATA:**
• Average: **{mu:.1f}** ({abs(gap):.1f} {"above" if gap > 0 else "below"} line)
• Buffer: **{buffer_pct:.0f}%** margin
• Model probability: **{prob*100:.0f}%**
• Hit rate: {f"{hit_rate:.0f}% ({recent_hits}/{recent_total} games)" if recent_hits else "N/A"}

📈 **WHY WE LIKE IT:**
{format_reasons_as_bullets(reasons)}

⚠️ **RISK FACTORS:**
{format_risks_as_bullets(risks)}

*[Technical: μ={mu:.1f}, σ={sigma:.1f}, z={(mu-line)/sigma if sigma > 0 else 0:+.2f}]*
"""
    
    # Optional LLM polish
    if use_llm:
        narrative = polish_with_llm(narrative, tier)
    
    return narrative


def polish_with_llm(text: str, tier: str) -> str:
    """
    Use Ollama/DeepSeek to add natural language polish
    
    This is OPTIONAL and adds personality to the report
    """
    # Best-effort load .env so filter scripts (run directly) can see DEEPSEEK_API_KEY.
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"), override=False)
    except Exception:
        pass

    # Prefer DeepSeek API when configured.
    deepseek_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if deepseek_key and deepseek_key != "your_deepseek_api_key_here":
        try:
            from observability.api_wrappers import fetch_deepseek_completion

            def _extract_number_tokens(s: str) -> set[str]:
                try:
                    import re

                    return set(re.findall(r"\d+(?:\.\d+)?", s or ""))
                except Exception:
                    return set()

            prompt = (
                "You are polishing a subscriber sports props report.\n"
                f"Tier: {tier}.\n"
                "Rules:\n"
                "- Keep the SAME structure and headings.\n"
                "- DO NOT change any numbers, lines, players, or statistics.\n"
                "- Improve flow and readability only.\n"
                "- Keep it concise.\n\n"
                f"TEXT TO POLISH:\n{text}"
            )
            polished = fetch_deepseek_completion(prompt, api_key=deepseek_key)
            if polished and isinstance(polished, str):
                polished = polished.strip()

                # Safety: ensure the model didn't ignore the input.
                required_markers = [
                    "🎯 **THE PLAY:**",
                    "📊 **THE DATA:**",
                    "📈 **WHY WE LIKE IT:**",
                    "⚠️ **RISK FACTORS:**",
                ]
                for m in required_markers:
                    if m in (text or "") and m not in polished:
                        print("[LLM] DeepSeek output dropped required section markers; using unpolished text")
                        return text

                orig_nums = _extract_number_tokens(text)
                pol_nums = _extract_number_tokens(polished)
                if orig_nums:
                    if not orig_nums.issubset(pol_nums):
                        print("[LLM] DeepSeek output failed numeric-preservation check; using unpolished text")
                        return text
                else:
                    # If there are no numbers, require that most of the original text appears.
                    core = (text or "").strip()
                    if core and core[:32] not in polished:
                        print("[LLM] DeepSeek output failed content-preservation check; using unpolished text")
                        return text

                return polished
        except Exception as e:
            print(f"[LLM] DeepSeek polish skipped: {e}")
            return text

    # If DeepSeek isn't configured, do NOT attempt localhost Ollama here.
    # The caller UI explicitly labels this as "DeepSeek"; falling back to a local
    # server causes confusing timeouts on machines without Ollama running.
    print("[LLM] DeepSeek API key not configured; polish skipped")
    return text


def enhance_report(picks: list, sport: str = "NBA", use_llm: bool = False, 
                   include_intro: bool = True, include_outro: bool = True) -> str:
    """
    Generate a full enhanced report from a list of picks
    
    Args:
        picks: List of pick dicts
        sport: Sport name for header
        use_llm: Whether to use LLM for polish (default: False)
        include_intro: Include FUOOM intro (default: True)
        include_outro: Include FUOOM outro (default: True)
    
    Returns:
        Full formatted report string
    """
    report_parts = []
    
    # Header
    date_str = datetime.now().strftime("%B %d, %Y")
    report_parts.append(f"# FUOOM DARK MATTER {sport.upper()} ANALYSIS")
    report_parts.append(f"## {date_str}")
    report_parts.append("")
    
    # Intro
    if include_intro:
        report_parts.append(FUOOM_INTRO)
        report_parts.append("")
    
    # Sort picks by tier (ELITE first)
    def tier_sort(p):
        prob = p.get('probability', p.get('final_probability', 0.50))
        return -prob  # Negative for descending sort
    
    sorted_picks = sorted(picks, key=tier_sort)
    
    # Group by tier
    elite_picks = [p for p in sorted_picks if (p.get('probability', p.get('final_probability', 0)) >= 0.75)]
    strong_picks = [p for p in sorted_picks if 0.65 <= (p.get('probability', p.get('final_probability', 0)) or 0) < 0.75]
    lean_picks = [p for p in sorted_picks if 0.55 <= (p.get('probability', p.get('final_probability', 0)) or 0) < 0.65]
    
    # Section: Elite Picks
    if elite_picks:
        report_parts.append("---")
        report_parts.append("## 🔥 ELITE TIER (75%+ Probability)")
        report_parts.append("")
        for pick in elite_picks:
            report_parts.append(enhance_pick_with_narrative(pick, use_llm))
            report_parts.append("")
    
    # Section: Strong Picks
    if strong_picks:
        report_parts.append("---")
        report_parts.append("## 💪 STRONG TIER (65-74% Probability)")
        report_parts.append("")
        for pick in strong_picks:
            report_parts.append(enhance_pick_with_narrative(pick, use_llm))
            report_parts.append("")
    
    # Section: Lean Picks
    if lean_picks:
        report_parts.append("---")
        report_parts.append("## 📊 LEAN TIER (55-64% Probability)")
        report_parts.append("")
        for pick in lean_picks:
            report_parts.append(enhance_pick_with_narrative(pick, use_llm))
            report_parts.append("")
    
    # Outro
    if include_outro:
        report_parts.append("---")
        report_parts.append(FUOOM_OUTRO)
    
    # Footer
    report_parts.append("")
    report_parts.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    report_parts.append("*FUOOM DARK MATTER v1.0 - Risk-First Quant Engine*")
    
    return "\n".join(report_parts)


def save_enhanced_report(picks: list, sport: str = "NBA", output_dir: str = "outputs",
                         use_llm: bool = False) -> str:
    """
    Generate and save enhanced report to file
    
    Returns: Path to saved file
    """
    report = enhance_report(picks, sport, use_llm)
    
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"FUOOM_{sport.upper()}_REPORT_{date_str}.md"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"[✓] Enhanced report saved: {filepath}")
    return filepath


if __name__ == "__main__":
    # Test with sample data
    test_picks = [
        {
            'player': 'RJ Barrett',
            'stat': '3pm',
            'line': 0.5,
            'direction': 'higher',
            'probability': 0.798,
            'mu': 1.6,
            'sigma': 1.3,
            'recent_hits': 8,
            'recent_total': 10,
            'opponent': 'ORL',
            'opponent_rank': 28,
        },
        {
            'player': 'Jaren Jackson Jr',
            'stat': '3pm',
            'line': 1.5,
            'direction': 'lower',
            'probability': 0.691,
            'mu': 1.3,
            'sigma': 1.1,
            'recent_hits': 7,
            'recent_total': 10,
            'opponent': 'DEN',
        },
        {
            'player': 'Tyler Herro',
            'stat': 'pra',
            'line': 27.5,
            'direction': 'under',
            'probability': 0.62,
            'mu': 25.1,
            'sigma': 6.2,
            'recent_hits': 6,
            'recent_total': 10,
            'opponent': 'SAC',
        }
    ]
    
    print("=" * 60)
    print("FUOOM DARK MATTER - TEST REPORT")
    print("=" * 60)
    
    report = enhance_report(test_picks, "NBA", use_llm=False)
    print(report)
