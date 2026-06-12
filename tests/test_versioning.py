from src.versioning import display_version, normalize_environment


def test_normalize_personal_environment_branches():
    assert normalize_environment(ref="leounib-dev") == "dev"
    assert normalize_environment(ref="leounib-nonprod") == "nonprod"
    assert normalize_environment(ref="leounib-main") == "prod"


def test_normalize_github_ref_names():
    assert normalize_environment(ref="refs/heads/dev") == "dev"
    assert normalize_environment(ref="refs/heads/nonprod") == "nonprod"
    assert normalize_environment(ref="refs/heads/main") == "prod"


def test_explicit_environment_wins_over_ref():
    assert normalize_environment(ref="leounib-dev", explicit="prod") == "prod"


def test_display_version_adds_environment_suffix():
    assert display_version("1.1.0", ref="leounib-dev") == "1.1.0-dev"
    assert display_version("1.1.0", ref="leounib-nonprod") == "1.1.0-nonprod"
    assert display_version("1.1.0", ref="leounib-main") == "1.1.0-prod"


def test_display_version_does_not_double_suffix():
    assert display_version("1.1.0-dev", ref="leounib-dev") == "1.1.0-dev"
