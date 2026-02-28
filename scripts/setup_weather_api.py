# Script to set up OpenWeatherMap API integration
import argparse

def main():
    parser = argparse.ArgumentParser(description="Setup OpenWeatherMap API access for golf tournaments.")
    parser.add_argument('--tournament', required=True, help='Tournament name')
    parser.add_argument('--location', required=True, help='Tournament location')
    args = parser.parse_args()
    print(f"Weather API setup for {args.tournament} at {args.location}")
    # TODO: Implement OpenWeatherMap API connection and data retrieval

if __name__ == "__main__":
    main()
