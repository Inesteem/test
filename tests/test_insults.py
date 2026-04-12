"""Tests for quiz/insults.py — pack loading and resolve_insult fallback chain."""

import json
from unittest.mock import MagicMock

from quiz.insults import (
    insult_pack_name,
    insult_pick,
    list_insult_packs,
    load_insult_pack,
    resolve_insult,
)


# ---------------------------------------------------------------------------
# list_insult_packs / shipped packs
# ---------------------------------------------------------------------------

class TestListInsultPacks:

    def test_returns_sorted_list(self):
        packs = list_insult_packs()
        assert packs == sorted(packs)

    def test_all_paths_end_with_json(self):
        for path in list_insult_packs():
            assert path.endswith(".json")


# ---------------------------------------------------------------------------
# insult_pack_name
# ---------------------------------------------------------------------------

class TestInsultPackName:

    def test_reads_name_field(self, tmp_path):
        path = tmp_path / "my-pack.json"
        path.write_text(json.dumps({"name": "My Display Name", "wrong": []}))
        assert insult_pack_name(str(path)) == "My Display Name"

    def test_falls_back_to_filename_without_name_field(self, tmp_path):
        path = tmp_path / "spicy.json"
        path.write_text(json.dumps({"wrong": []}))
        assert insult_pack_name(str(path)) == "spicy"

    def test_malformed_json_falls_back_to_filename(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{ not valid json")
        assert insult_pack_name(str(path)) == "broken"

    def test_missing_file_falls_back_to_filename(self):
        assert insult_pack_name("/nonexistent/my-pack.json") == "my-pack"


# ---------------------------------------------------------------------------
# load_insult_pack
# ---------------------------------------------------------------------------

class TestLoadInsultPack:

    def test_loads_all_categories(self, tmp_path):
        path = tmp_path / "pack.json"
        data = {
            "correct_fast": ["A"],
            "correct_slow": ["B"],
            "wrong": ["C"],
            "timeout": ["D"],
            "nobody": ["E"],
        }
        path.write_text(json.dumps(data))
        pack = load_insult_pack(str(path))
        for cat, expected in data.items():
            assert pack[cat] == expected

    def test_missing_categories_default_to_empty(self, tmp_path):
        path = tmp_path / "pack.json"
        path.write_text(json.dumps({"wrong": ["X"]}))
        pack = load_insult_pack(str(path))
        assert pack["wrong"] == ["X"]
        assert pack["correct_fast"] == []
        assert pack["nobody"] == []


# ---------------------------------------------------------------------------
# insult_pick
# ---------------------------------------------------------------------------

class TestInsultPick:

    def test_picks_from_pool(self):
        pack = {"wrong": ["only one option"]}
        assert insult_pick(pack, "wrong") == "only one option"

    def test_empty_pool_returns_empty_string(self):
        pack = {"wrong": []}
        assert insult_pick(pack, "wrong") == ""

    def test_missing_category_returns_empty_string(self):
        pack = {"wrong": ["x"]}
        assert insult_pick(pack, "timeout") == ""

    def test_none_pack_returns_empty_string(self):
        assert insult_pick(None, "wrong") == ""


# ---------------------------------------------------------------------------
# resolve_insult — the fallback chain
# ---------------------------------------------------------------------------

class TestResolveInsult:

    def test_ai_result_preferred(self):
        ai = MagicMock()
        ai.generate_insult.return_value = "AI said this"
        pack = {"wrong": ["static"]}
        assert resolve_insult("wrong", insult_ai_obj=ai, insult_pack=pack) == "AI said this"

    def test_empty_ai_falls_through_to_pack(self):
        ai = MagicMock()
        ai.generate_insult.return_value = ""
        pack = {"wrong": ["static"]}
        assert resolve_insult("wrong", insult_ai_obj=ai, insult_pack=pack) == "static"

    def test_ai_exception_falls_through_to_pack(self):
        ai = MagicMock()
        ai.generate_insult.side_effect = RuntimeError("subprocess crashed")
        pack = {"wrong": ["static fallback"]}
        result = resolve_insult("wrong", insult_ai_obj=ai, insult_pack=pack)
        assert result == "static fallback"

    def test_neither_source_returns_empty(self):
        assert resolve_insult("wrong") == ""
        assert resolve_insult("wrong", insult_pack={}) == ""
        assert resolve_insult("wrong", insult_pack={"wrong": []}) == ""

    def test_ai_kwargs_forwarded(self):
        ai = MagicMock()
        ai.generate_insult.return_value = "ok"
        resolve_insult("wrong", insult_ai_obj=ai,
                       question="Q?", team_name="Foxes")
        ai.generate_insult.assert_called_once_with(
            "wrong", question="Q?", team_name="Foxes",
        )
