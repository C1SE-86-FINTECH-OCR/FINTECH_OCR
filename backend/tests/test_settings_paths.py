import hashlib
from pathlib import Path
from app.core import BACKEND_DIR, Settings


def test_backend_env_configuration_is_independent_of_working_directory(monkeypatch,tmp_path):
    def fingerprint():
        settings=Settings()
        return hashlib.sha256(repr((settings.database_url,settings.jwt_secret,settings.upload_dir)).encode()).hexdigest()
    monkeypatch.chdir(BACKEND_DIR)
    expected=fingerprint()
    monkeypatch.chdir(tmp_path)
    assert fingerprint()==expected
    assert Path(Settings.model_config['env_file']).is_absolute()
