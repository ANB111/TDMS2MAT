"""
Tests for tdms2mat.config.schema (AppConfig) and tdms2mat.config.config_utils.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tdms2mat.config.config_utils import load_config, save_config, validate_config
from tdms2mat.config.schema import AppConfig


# ---------------------------------------------------------------------------
# AppConfig construction
# ---------------------------------------------------------------------------


class TestAppConfigConstruction:
    def test_defaults_produce_valid_model(self) -> None:
        """AppConfig() with no arguments should give a model with safe defaults."""
        cfg = AppConfig()
        assert cfg.FS == 10
        assert cfg.n_channels == 16
        assert cfg.timezone_offset_hours == -3
        assert cfg.csv_decimal_separator == "."

    def test_minimal_dict_accepted(self, minimal_config_dict: dict) -> None:
        cfg = AppConfig.model_validate(minimal_config_dict)
        assert cfg.input_folder == "/tmp/in"
        assert cfg.output_folder == "/tmp/out"

    def test_extra_keys_ignored(self, minimal_config_dict: dict) -> None:
        """Old config files may have unknown keys — they must not raise."""
        d = dict(minimal_config_dict)
        d["old_unused_key"] = "value"
        cfg = AppConfig.model_validate(d)
        assert not hasattr(cfg, "old_unused_key")

    def test_fs_coerced_from_string(self) -> None:
        """tkinter StringVar passes FS as a string; AppConfig must coerce it."""
        cfg = AppConfig.model_validate({"FS": "20"})
        assert cfg.FS == 20
        assert isinstance(cfg.FS, int)

    def test_n_channels_coerced_from_string(self) -> None:
        cfg = AppConfig.model_validate({"n_channels": "8"})
        assert cfg.n_channels == 8

    def test_invalid_fs_raises(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig.model_validate({"FS": "not_a_number"})

    def test_invalid_decimal_separator_raises(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig.model_validate({"csv_decimal_separator": ";"})

    def test_comma_decimal_separator_accepted(self) -> None:
        cfg = AppConfig.model_validate({"csv_decimal_separator": ","})
        assert cfg.csv_decimal_separator == ","

    def test_to_legacy_dict_round_trip(self) -> None:
        cfg = AppConfig(FS=25, n_channels=8, timezone_offset_hours=-5)
        d = cfg.to_legacy_dict()
        assert isinstance(d, dict)
        assert d["FS"] == 25
        assert d["n_channels"] == 8
        assert d["timezone_offset_hours"] == -5

    def test_output_path_returns_path(self, tmp_dir: Path) -> None:
        cfg = AppConfig(output_folder=str(tmp_dir))
        assert cfg.output_path() == tmp_dir

    def test_selected_files_default_is_empty_list(self) -> None:
        cfg = AppConfig()
        assert cfg.selected_files == []


# ---------------------------------------------------------------------------
# validate_config helper
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def test_empty_folders_fail(self) -> None:
        cfg = AppConfig()  # all folders are ""
        assert validate_config(cfg) is False

    def test_non_empty_folders_pass(self, minimal_config_dict: dict) -> None:
        cfg = AppConfig.model_validate(minimal_config_dict)
        assert validate_config(cfg) is True


# ---------------------------------------------------------------------------
# load_config / save_config round-trip
# ---------------------------------------------------------------------------


class TestConfigFilePersistence:
    def test_save_and_load_round_trip(self, tmp_dir: Path) -> None:
        cfg_path = tmp_dir / "config.json"
        cfg = AppConfig(
            input_folder=str(tmp_dir / "in"),
            output_folder=str(tmp_dir / "out"),
            excel_output_folder=str(tmp_dir / "excel"),
            FS=100,
            n_channels=8,
            timezone_offset_hours=0,
        )
        save_config(cfg, str(cfg_path))

        loaded = load_config(str(cfg_path))
        assert loaded.FS == 100
        assert loaded.n_channels == 8
        assert loaded.timezone_offset_hours == 0

    def test_save_creates_file(self, tmp_dir: Path) -> None:
        cfg_path = tmp_dir / "cfg.json"
        assert not cfg_path.exists()
        save_config(AppConfig(), str(cfg_path))
        assert cfg_path.exists()

    def test_load_returns_default_on_missing_file(self, tmp_dir: Path) -> None:
        missing = str(tmp_dir / "does_not_exist.json")
        cfg = load_config(missing)
        # Must return an AppConfig with defaults, not raise
        assert isinstance(cfg, AppConfig)
        assert cfg.FS == 10

    def test_load_returns_default_on_corrupt_json(self, tmp_dir: Path) -> None:
        bad_cfg = tmp_dir / "bad.json"
        bad_cfg.write_text("this is not json{{{{")
        cfg = load_config(str(bad_cfg))
        assert isinstance(cfg, AppConfig)

    def test_save_creates_backup(self, tmp_dir: Path) -> None:
        cfg_path = tmp_dir / "config.json"
        # Write once to create original
        save_config(AppConfig(FS=10), str(cfg_path))
        # Write again — should create .bak
        save_config(AppConfig(FS=20), str(cfg_path))
        bak_path = tmp_dir / "config.json.bak"
        assert bak_path.exists()

    def test_saved_file_is_valid_json(self, tmp_dir: Path) -> None:
        cfg_path = tmp_dir / "config.json"
        save_config(AppConfig(), str(cfg_path))
        with open(cfg_path) as f:
            data = json.load(f)
        assert "FS" in data
        assert "n_channels" in data
