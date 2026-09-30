from ncig import cli


def test_v0171_sync_harvest_symbol_is_imported():
    assert callable(cli.sync_github_harvest)
