# Script to set up DataGolf API integration
import argparse

def main():
    parser = argparse.ArgumentParser(description="Setup DataGolf API access.")
    parser.add_argument('--api_key', required=True, help='Your DataGolf API key')
    args = parser.parse_args()
    print(f"DataGolf API key set: {args.api_key}")
    # TODO: Implement DataGolf API connection and data download

if __name__ == "__main__":
    main()
