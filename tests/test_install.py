"""Tests for fettle.install — hook and config installation helpers."""

from fettle.install import install_config, install_ignore


class TestInstallConfig:
    def test_creates_fettle_toml(self, tmp_path, capsys):
        install_config(tmp_path)
        assert (tmp_path / ".fettle.toml").is_file()
        content = (tmp_path / ".fettle.toml").read_text()
        assert "[gates" in content

    def test_does_not_overwrite_existing(self, tmp_path, capsys):
        (tmp_path / ".fettle.toml").write_text("[custom]\nx = 1\n")
        install_config(tmp_path)
        content = (tmp_path / ".fettle.toml").read_text()
        assert "[custom]" in content
        assert "already exists" in capsys.readouterr().out


class TestInstallIgnore:
    def test_creates_ignore_file(self, tmp_path, capsys):
        install_ignore(tmp_path)
        assert (tmp_path / ".fettle-ignore").is_file()

    def test_does_not_overwrite_existing(self, tmp_path, capsys):
        (tmp_path / ".fettle-ignore").write_text("mypattern\n")
        install_ignore(tmp_path)
        content = (tmp_path / ".fettle-ignore").read_text()
        assert "mypattern" in content
