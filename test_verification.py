from src.stats_verification.integration import get_verification_system


def main():
    system = get_verification_system()

    # Test with a player
    stats = system.get_player_stats(
        player="Jonas Valanciunas",
        game_date="2026-01-02",
        stat_type="points",
        immediate_only=False,
    )

    print("Stats:", stats)
    print("System status:", system.get_system_status())


if __name__ == "__main__":
    main()
