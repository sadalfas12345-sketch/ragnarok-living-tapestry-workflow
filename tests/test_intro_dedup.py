import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from batch_01.batch_runner import add_character_intro, effective_scene_caption, normalize_text, validate_spec


def test_intros_are_added_once_and_do_not_cascade_into_places():
    source = Path(__file__).resolve().parents[1] / "batch_01/source/37_gilgamesh_enkidu.json"
    spec = json.loads(source.read_text(encoding="utf-8"))
    prior = []
    effective = []
    for index, scene in enumerate(spec["scenes"]):
        caption = normalize_text(scene["caption"])
        caption = effective_scene_caption(spec, index, caption, prior)
        caption = add_character_intro(caption, prior)
        effective.append(caption)
        prior.append(caption)

    joined = " ".join(effective).lower()
    assert joined.count("the king of uruk") == 1
    # Uruk is already introduced inside Gilgamesh's role; it must not trigger
    # a second nested place introduction during the same pass.
    assert joined.count("the city gilgamesh rules") == 0
    assert joined.count("a wild man turned friend") == 1


def test_source_validation_accepts_episode_37_without_intro_repeat_errors():
    source = Path(__file__).resolve().parents[1] / "batch_01/source/37_gilgamesh_enkidu.json"
    spec = json.loads(source.read_text(encoding="utf-8"))
    assert not [error for error in validate_spec(spec) if "intro" in error]
