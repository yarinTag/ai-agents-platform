"""Explicit permission-lab setup; never invoked by API startup."""
import argparse
import json
from demo_data import setup_access_lab

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Add two isolated permission-lab organizations to an existing database.')
    parser.add_argument('--database', required=True)
    parser.add_argument('--credentials', required=True, help='New private credential file outside the repository')
    parser.add_argument('--apply', action='store_true', help='Explicitly authorize additive database registration')
    args = parser.parse_args()
    if not args.apply:
        parser.error('--apply is required; setup never runs implicitly')
    print(json.dumps(setup_access_lab(args.database, args.credentials), indent=2))
