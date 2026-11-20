"""Explicit configuration preview/import tool. Never starts the application."""
import argparse
import json
import os

from storage.configuration_snapshot import MigrationConflict, extract_configuration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Explicit SQLite snapshot path')
    parser.add_argument('--organization', required=True)
    parser.add_argument('--max-rows', type=int, default=100000)
    parser.add_argument('--profile', choices=('configuration', 'execution-history'),
                        default='configuration')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--schema')
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    if args.apply and (not args.schema or not args.expected_sha256):
        parser.error('--apply requires --schema and --expected-sha256 from the preview')
    if not args.apply and (args.schema or args.expected_sha256):
        parser.error('Target schema and expected hash are only used with --apply')
    try:
        extractor = extract_configuration
        if args.profile == 'execution-history':
            from storage.execution_snapshot import extract_execution_history
            extractor = extract_execution_history
        snapshot = extractor(args.source, args.organization, max_rows=args.max_rows)
        if args.apply:
            from storage.configuration_postgres import ConfigurationMigration
            from storage.runner_postgres import connection_factory
            dsn = os.environ.get('CONFIGURATION_MIGRATION_DSN')
            if not dsn:
                raise MigrationConflict('Explicit CONFIGURATION_MIGRATION_DSN required.')
            migration_class = ConfigurationMigration
            if args.profile == 'execution-history':
                from storage.execution_postgres import ExecutionHistoryMigration
                migration_class = ExecutionHistoryMigration
            result = migration_class(connection_factory(dsn), args.schema).apply(
                snapshot, expected_sha256=args.expected_sha256)
        else:
            result = snapshot.report()
        print(json.dumps(result, sort_keys=True, indent=2))
    except MigrationConflict as exc:
        parser.exit(2, str(exc) + '\n')
    except (OSError, ValueError, ImportError):
        # No DSNs, database rows, ciphertext, tokens or exception chains in reports.
        parser.exit(2, 'Configuration migration failed; check source and driver setup.\n')


if __name__ == '__main__':
    main()
