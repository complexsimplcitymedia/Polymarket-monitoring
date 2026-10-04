import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("set_env", Path(__file__).parent.parent / "scripts" / "_set_env.py")
set_env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(set_env)


def test_replaces_existing_keys_appends_new_ones_and_keeps_the_rest(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DEBUG=true\n# a comment\nSMTP_HOST=old\nOTHER=1\n")
    set_env.set_keys(env, {"SMTP_HOST": "smtp.hostinger.com", "SMTP_PORT": "465"})
    lines = env.read_text().splitlines()
    assert 'SMTP_HOST="smtp.hostinger.com"' in lines and 'SMTP_PORT="465"' in lines
    assert "DEBUG=true" in lines and "# a comment" in lines and "OTHER=1" in lines
    assert sum(1 for line in lines if line.startswith("SMTP_HOST=")) == 1  # replaced, not duplicated


def test_awkward_passwords_survive_a_round_trip_through_the_app_settings(tmp_path):
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class S(BaseSettings):
        model_config = SettingsConfigDict(env_file=str(tmp_path / ".env"), extra="ignore")
        SMTP_PASSWORD: str = ""

    password = 'p@ss w0rd #1 $HOME "quoted" \\back'
    set_env.set_keys(tmp_path / ".env", {"SMTP_PASSWORD": password})
    assert S().SMTP_PASSWORD == password
