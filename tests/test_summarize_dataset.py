from pathlib import Path

import yaml

from cam_recorder.summarize_dataset import parse_bag_name, resolve_dataset_base


def test_parse_bag_name_extracts_scenario_and_time():
    result = parse_bag_name(
        Path("Jul27_Scenario_8_4_2026-07-27_12-01-36_0.mcap")
    )

    assert result == {
        "scenario_id": "8",
        "sub_id": "4",
        "scenario_key": "8_4",
        "recording_datetime": "2026-07-27T12:01:36",
    }


def test_parse_unknown_name_returns_blank_identifiers():
    result = parse_bag_name(Path("recording.mcap"))

    assert result["scenario_id"] == ""
    assert result["sub_id"] == ""


def test_resolve_dataset_base_from_config(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump({"data": {"dataset_base": str(dataset)}}),
        encoding="utf-8",
    )

    assert resolve_dataset_base(None, config) == dataset
