#!/usr/bin/env python3
"""Reusable Living Tapestries Batch 01 pipeline.

The episode JSON is the only editorial source.  The final narration waveform is
the only timing source.  Ragnarök files in the repository are intentionally not
imported by this runner.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
WORK = ROOT / "episodes"
FEEDBACK_POLICY = json.loads((ROOT.parent / "production_feedback_gates.json").read_text(encoding="utf-8"))
MAX_HORIZONTAL_TRAVEL_RATE = float(FEEDBACK_POLICY["camera"]["max_normalized_travel_per_second"])
PRONUNCIATION_LEXICON = json.loads((ROOT / "pronunciation_lexicon.json").read_text(encoding="utf-8"))
CHARACTER_INTRO_LEXICON = json.loads((ROOT / "character_intro_lexicon.json").read_text(encoding="utf-8"))
CHARACTER_INTRO_POLICY = FEEDBACK_POLICY.get("character_intros", {})
MOJIBAKE_REPLACEMENTS = {
    "â€™": "'",
    "â€˜": "'",
    "â€œ": '"',
    "â€\u009d": '"',
    "â€“": "-",
    "â€”": "—",
    "Â": "",
}
MOJIBAKE_EXTRA_REPLACEMENTS = {
    "Ã¢â‚¬Â": '"',
    "Ã¢â‚¬â€”": "—",
}
MOJIBAKE_REPLACEMENTS.update(MOJIBAKE_EXTRA_REPLACEMENTS)
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")
RATE = 24000
VOICE = os.environ.get("LIVING_TAPESTRIES_VOICE", "en-US-AvaNeural")
SUBTITLE_MODE = os.environ.get("LIVING_TAPESTRIES_SUBTITLE_MODE", "burned")

MUSIC_PROFILES = {
    "default": [
        {"title": "Epical Drums 05", "artist": "Grigoriy Nuzhny", "url": "https://mixkit.co/free-stock-music/orchestral-hybrid/", "file": "mixkit_epical_drums_05_grigoriy_nuzhny.mp3"},
        {"title": "Epic Games", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/mood/tension/", "file": "mixkit_epic_games_ahjay_stelino.mp3"},
        {"title": "A New Life", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/orchestral-hybrid/", "file": "mixkit_a_new_life_eugenio_mininni.mp3"},
    ],
    3: [
        {"title": "Fright Night", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/mood/suspenseful/", "file": "mixkit_fright_night_michael_ramir_c.mp3"},
        {"title": "Valley Sunset", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_valley_sunset_alejandro_magana.mp3"},
        {"title": "Silent Descent", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_silent_descent_eugenio_mininni.mp3"},
    ],
    4: [
        {"title": "Sun and His Daughter", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_sun_and_his_daughter_eugenio_mininni.mp3"},
        {"title": "Discover", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_discover_eugenio_mininni.mp3"},
        {"title": "Spirit in the Woods", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_spirit_in_the_woods_alejandro_magana.mp3"},
    ],
    5: [
        {"title": "Fallen (Asper)", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_fallen_asper_eugenio_mininni.mp3"},
        {"title": "Tapis", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_tapis_eugenio_mininni.mp3"},
        {"title": "Echoes", "artist": "Andrew Ev", "url": "https://mixkit.co/free-stock-music/mood/suspenseful/", "file": "mixkit_echoes_andrew_ev.mp3"},
    ],
    6: [
        {"title": "Fright Night (Version 2)", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/mood/suspenseful/", "file": "mixkit_fright_night_michael_ramir_c_v2.mp3"},
        {"title": "Romantic 03", "artist": "Lily J", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_romantic_03_lily_j.mp3"},
        {"title": "Forest Treasure", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_forest_treasure_alejandro_magana.mp3"},
    ],
    7: [
        {"title": "Hip Hop 02", "artist": "Lily J", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_hip_hop_02_lily_j.mp3"},
        {"title": "Hazy After Hours", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_hazy_after_hours_alejandro_magana.mp3"},
        {"title": "Tech House vibes", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_tech_house_vibes_alejandro_magana.mp3"},
    ],
    8: [
        {"title": "Deep Urban", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_deep_urban_eugenio_mininni.mp3"},
        {"title": "Secret Garden", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_secret_garden_eugenio_mininni.mp3"},
        {"title": "Piano Horror", "artist": "Francisco Alvear", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_piano_horror_francisco_alvear.mp3"},
    ],
    9: [
        {"title": "Epical Drums 01", "artist": "Grigoriy Nuzhny", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_epical_drums_01_grigoriy_nuzhny.mp3"},
        {"title": "Sports Highlights", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_sports_highlights_ahjay_stelino.mp3"},
        {"title": "Complicated", "artist": "Arulo", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_complicated_arulo.mp3"},
    ],
    10: [
        {"title": "Can't Get You Off My Mind", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_cant_get_you_off_my_mind_michael_ramir_c.mp3"},
        {"title": "Romantic", "artist": "Francisco Alvear", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_romantic_francisco_alvear.mp3"},
        {"title": "Latin Lovers", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_latin_lovers_ahjay_stelino.mp3"},
    ],
    11: [
        {"title": "Gimme that Groove!", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_gimme_that_groove_michael_ramir_c.mp3"},
        {"title": "Beautiful Dream", "artist": "Diego Nava", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_beautiful_dream_diego_nava.mp3"},
        {"title": "Driving Ambition", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_driving_ambition_ahjay_stelino.mp3"},
    ],
    12: [
        {"title": "Cat Walk", "artist": "Arulo", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_cat_walk_arulo.mp3"},
        {"title": "Night Sky Hip Hop", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_night_sky_hip_hop_michael_ramir_c.mp3"},
        {"title": "Praise the Lord", "artist": "Arulo", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_praise_the_lord_arulo.mp3"},
    ],
    13: [
        {"title": "C.B.P.D", "artist": "Arulo", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_cbpd_arulo.mp3"},
        {"title": "Pop 05", "artist": "Grigoriy Nuzhny", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_pop_05_grigoriy_nuzhny.mp3"},
        {"title": "Villa Penthouse", "artist": "Arulo", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_villa_penthouse_arulo.mp3"},
    ],
    14: [
        {"title": "Wedding 01", "artist": "Francisco Alvear", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_wedding_01_francisco_alvear.mp3"},
        {"title": "Dirty Thinkin'", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_dirty_thinkin_michael_ramir_c.mp3"},
        {"title": "Island Beat", "artist": "Arulo", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_island_beat_arulo.mp3"},
    ],
    15: [
        {"title": "A Very Happy Christmas", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_a_very_happy_christmas_michael_ramir_c.mp3"},
        {"title": "Sleepy Cat", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_sleepy_cat_alejandro_magana.mp3"},
        {"title": "Romantic 05", "artist": "Lily J", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_romantic_05_lily_j.mp3"},
    ],
    16: [
        {"title": "Relaxing Country", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/mood/relaxing/", "file": "mixkit_relaxing_country_ahjay_stelino.mp3"},
        {"title": "Relaxing in Nature", "artist": "Diego Nava", "url": "https://mixkit.co/free-stock-music/mood/relaxing/", "file": "mixkit_relaxing_in_nature_diego_nava.mp3"},
        {"title": "Look At The Bright Side", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/mood/bright/", "file": "mixkit_look_at_the_bright_side_michael_ramir_c.mp3"},
    ],
    17: [
        {"title": "Chill Bro", "artist": "Diego Nava", "url": "https://mixkit.co/free-stock-music/mood/chill/", "file": "mixkit_chill_bro_diego_nava.mp3"},
        {"title": "Just Chill", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/mood/chill/", "file": "mixkit_just_chill_ahjay_stelino.mp3"},
        {"title": "Recline and Chill", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/mood/chill/", "file": "mixkit_recline_and_chill_ahjay_stelino.mp3"},
    ],
    18: [
        {"title": "Tears of Joy", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_tears_of_joy_michael_ramir_c.mp3"},
        {"title": "The Long Road", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_the_long_road_ahjay_stelino.mp3"},
        {"title": "BRIDGE N° 98", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_bridge_98_eugenio_mininni.mp3"},
    ],
    19: [
        {"title": "Dark Shadows", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/traditional/", "file": "mixkit_dark_shadows_ahjay_stelino.mp3"},
        {"title": "Indian Meditations", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/traditional/", "file": "mixkit_indian_meditations_ahjay_stelino.mp3"},
        {"title": "Nield Grohm Hanging 4", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_nield_grohm_hanging_4_eugenio_mininni.mp3"},
    ],
    20: [
        {"title": "Ode to Loneliness", "artist": "Diego Nava", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_ode_to_loneliness_diego_nava.mp3"},
        {"title": "The Journey", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_the_journey_ahjay_stelino.mp3"},
        {"title": "We'll Be Okay", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_well_be_okay_michael_ramir_c.mp3"},
    ],
    21: [
        {"title": "Forever Love", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_forever_love_ahjay_stelino.mp3"},
        {"title": "Wedding Harp", "artist": "Francisco Alvear", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_wedding_harp_francisco_alvear.mp3"},
        {"title": "Classical vibes 2", "artist": "Grigoriy Nuzhny", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_classical_vibes_2_grigoriy_nuzhny.mp3"},
    ],
    22: [
        {"title": "Classical vibes 4", "artist": "Grigoriy Nuzhny", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_classical_vibes_4_grigoriy_nuzhny.mp3"},
        {"title": "Skyline", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_skyline_eugenio_mininni.mp3"},
        {"title": "Fragments Of Bangkok", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_fragments_of_bangkok_eugenio_mininni.mp3"},
    ],
    23: [
        {"title": "Classical 3", "artist": "Jonny S.", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_classical_3_jonny_s.mp3"},
        {"title": "Dreaming Big", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_dreaming_big_ahjay_stelino.mp3"},
        {"title": "Classical vibes 3", "artist": "Grigoriy Nuzhny", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_classical_vibes_3_grigoriy_nuzhny.mp3"},
    ],
    24: [
        {"title": "Unforgiven", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_unforgiven_michael_ramir_c.mp3"},
        {"title": "Torn Threads", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_torn_threads_ahjay_stelino.mp3"},
        {"title": "Staring at the Night Sky", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_staring_at_the_night_sky_alejandro_magana.mp3"},
    ],
    25: [
        {"title": "Delirium", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_delirium_eugenio_mininni.mp3"},
        {"title": "Piano Horror", "artist": "Francisco Alvear", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_piano_horror_francisco_alvear.mp3"},
        {"title": "Staring at the Night Sky", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_staring_at_the_night_sky_alejandro_magana.mp3"},
    ],
    26: [
        {"title": "Feedback Dreams", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_feedback_dreams_eugenio_mininni.mp3"},
        {"title": "Deep Urban", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_deep_urban_eugenio_mininni.mp3"},
        {"title": "Selpan", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_selpan_eugenio_mininni.mp3"},
    ],
    27: [
        {"title": "Wake Up Now", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/traditional/", "file": "mixkit_wake_up_now_michael_ramir_c.mp3"},
        {"title": "A Decade in Beijing", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/traditional/", "file": "mixkit_a_decade_in_beijing_michael_ramir_c.mp3"},
        {"title": "Sicilian Coffee", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_sicilian_coffee_eugenio_mininni.mp3"},
    ],
    28: [
        {"title": "Serene View", "artist": "Arulo", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_serene_view_arulo.mp3"},
        {"title": "Romantic", "artist": "Francisco Alvear", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_romantic_francisco_alvear.mp3"},
        {"title": "Sports Highlights", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_sports_highlights_ahjay_stelino.mp3"},
    ],
    29: [
        {"title": "Nield Grohm Hanging 1", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_nield_grohm_hanging_1_eugenio_mininni.mp3"},
        {"title": "Oscar el Asesino", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_oscar_el_asesino_michael_ramir_c.mp3"},
        {"title": "Never Say Die", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_never_say_die_michael_ramir_c.mp3"},
    ],
    30: [
        {"title": "I Won't surrender", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_i_wont_surrender_michael_ramir_c.mp3"},
        {"title": "Life's a Movie", "artist": "Arulo", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_lifes_a_movie_arulo.mp3"},
        {"title": "Miss You", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_miss_you_eugenio_mininni.mp3"},
    ],
}

# Episode 25's third cue is overridden here because the original catalog entry
# was already used by an earlier rendered episode.
MUSIC_PROFILES[25][2] = {"title": "Games Worldbeat", "artist": "Bernardo R.", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_games_worldbeat_bernardo_r.mp3"}

# Episode 06 uses a distinct licensed trio so the soundtrack QA gate can
# distinguish this rebuild from earlier episode renders.
MUSIC_PROFILES[6] = [
    {"title": "Fright Night (Version 2)", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/mood/suspenseful/", "file": "mixkit_fright_night_michael_ramir_c_v2.mp3"},
    {"title": "Romantic 03", "artist": "Lily J", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_romantic_03_lily_j.mp3"},
    {"title": "Gold Virginia", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_gold_virginia_eugenio_mininni.mp3"},
]
MUSIC_PROFILES[7] = [
    {"title": "Nield Grohm Hanging 1", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_nield_grohm_hanging_1_eugenio_mininni.mp3"},
    {"title": "Oscar el Asesino", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_oscar_el_asesino_michael_ramir_c.mp3"},
    {"title": "Never Say Die", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_never_say_die_michael_ramir_c.mp3"},
]
MUSIC_PROFILES[8] = [
    {"title": "I Won't Surrender", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_i_wont_surrender_michael_ramir_c.mp3"},
    {"title": "Life's a Movie", "artist": "Arulo", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_lifes_a_movie_arulo.mp3"},
    {"title": "Miss You", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/film-score/", "file": "mixkit_miss_you_eugenio_mininni.mp3"},
]
MUSIC_PROFILES[9] = [
    {"title": "Nield Grohm Hanging 2", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_nield_grohm_hanging_2_eugenio_mininni.mp3"},
    {"title": "Nield Grohm Hanging 3", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/world-fusion/", "file": "mixkit_nield_grohm_hanging_3_eugenio_mininni.mp3"},
    {"title": "Relax", "artist": "Francisco Alvear", "url": "https://mixkit.co/free-stock-music/mood/relaxing/", "file": "mixkit_relax_francisco_alvear.mp3"},
]
MUSIC_PROFILES[10] = [
    {"title": "Forest Treasure", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_forest_treasure_alejandro_magana.mp3"},
    {"title": "Epical Drums 01", "artist": "Grigoriy Nuzhny", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_epical_drums_01_grigoriy_nuzhny.mp3"},
    {"title": "Secret Garden", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_secret_garden_eugenio_mininni.mp3"},
]


def run(cmd: list[str], *, capture=False) -> str:
    p = subprocess.run(cmd, check=True, text=True, capture_output=capture)
    return p.stdout if capture else ""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def duration(path: Path) -> float:
    out = run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture=True)
    return float(json.loads(out)["format"]["duration"])


def load_episode(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def episode_paths(ep: int) -> tuple[Path, Path]:
    spec_path = sorted(SOURCE.glob(f"{ep:02d}_*.json"))[0]
    return spec_path, WORK / f"{ep:02d}_{spec_path.stem[3:]}"


def source_files() -> list[Path]:
    return sorted(SOURCE.glob("[0-9][0-9]_*.json"))


def validate_spec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pronunciation_policy = FEEDBACK_POLICY.get("pronunciation", {})
    intro_policy = FEEDBACK_POLICY.get("character_intros", {})
    if intro_policy.get("enabled", True):
        max_intro_words = int(intro_policy.get("max_inserted_words", 6))
        forbidden_intro_terms = [str(x).lower() for x in intro_policy.get("forbidden_outcome_terms", [])]
        for name, intro in CHARACTER_INTRO_LEXICON.items():
            intro_words = str(intro).split()
            if len(intro_words) > max_intro_words:
                errors.append(f"character intro for {name} exceeds {max_intro_words} words")
            if intro_policy.get("spoiler_free", True):
                for term in forbidden_intro_terms:
                    if re.search(rf"\b{re.escape(term)}\b", str(intro).lower()):
                        errors.append(f"character intro for {name} contains spoiler outcome term {term!r}")
    if pronunciation_policy.get("reject_empty_overrides"):
        for written, phonetic in PRONUNCIATION_LEXICON.items():
            if not str(written).strip() or not str(phonetic).strip():
                errors.append(f"empty pronunciation override for {written!r}")
    if pronunciation_policy.get("reject_letter_by_letter_overrides"):
        for written, phonetic in PRONUNCIATION_LEXICON.items():
            if re.fullmatch(r"(?:[A-Za-z]\s+){1,}[A-Za-z]", str(phonetic).strip()):
                errors.append(f"letter-by-letter pronunciation override for {written!r}")
    required = ["schema_version", "episode_number", "title", "civilization", "source_integrity", "format", "runtime", "image_reference", "audio", "scenes"]
    errors.extend(f"missing top-level field: {k}" for k in required if k not in spec)
    if spec.get("schema_version") != "living_tapestry_story_v1":
        errors.append("unsupported schema_version")
    scenes = spec.get("scenes", [])
    if len(scenes) != 6:
        errors.append(f"expected 6 scenes, found {len(scenes)}")
    # The authoritative story JSON owns the opening hook.  It must be the
    # first spoken/captioned text, and it must not be duplicated in another
    # scene.  Fail before any narration, art, or render work if the source
    # has drifted from that contract.
    if scenes:
        first_caption = str(scenes[0].get("caption", "")).strip()
        hook_count = sum(1 for scene in scenes if re.match(r"^What if\b", str(scene.get("caption", "")).strip(), re.IGNORECASE))
        if not re.match(r"^What if\b", first_caption, re.IGNORECASE):
            errors.append("scene 1 must begin with the authoritative What if hook")
        if hook_count != 1:
            errors.append(f"expected exactly one What if hook in scene captions, found {hook_count}")
    seen = set()
    for i, scene in enumerate(scenes, 1):
        for k in ("id", "asset", "caption", "image_prompt", "camera", "music", "sfx", "pause_after_seconds_hint"):
            if k not in scene:
                errors.append(f"scene {i} missing {k}")
        if scene.get("id") in seen:
            errors.append(f"duplicate scene id: {scene.get('id')}")
        seen.add(scene.get("id"))
        if not isinstance(scene.get("caption"), str) or not scene.get("caption", "").strip():
            errors.append(f"scene {i} caption is empty")
        try:
            pause = float(scene.get("pause_after_seconds_hint"))
            if not 0.0 <= pause <= 3.0:
                errors.append(f"scene {i} pause hint outside 0-3 seconds")
        except (TypeError, ValueError):
            errors.append(f"scene {i} pause hint is not numeric")
    si = spec.get("source_integrity", {})
    if not si.get("classification") or not si.get("research_status"):
        errors.append("source_integrity must include classification and research_status")
    if spec.get("image_reference", {}).get("status") != "GENERATE_BEFORE_RENDER":
        errors.append("image_reference.status must require a generated style board")
    if not isinstance(spec.get("audio", {}).get("mix"), dict):
        errors.append("audio.mix must be an object")
    return errors


def validate_all() -> dict[str, Any]:
    reports = []
    for path in source_files():
        spec = load_episode(path)
        errors = validate_spec(spec)
        reports.append({"episode": spec.get("episode_number"), "file": path.name, "title": spec.get("title"), "errors": errors, "status": "PASS" if not errors else "FAIL"})
    report = {"schema": "living_tapestry_batch_validation_v1", "count": len(reports), "reports": reports, "status": "PASS" if all(not x["errors"] for x in reports) else "FAIL"}
    (ROOT / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = []
    for path in source_files():
        spec = load_episode(path)
        si = spec.get("source_integrity", {})
        audit.append({"episode": spec.get("episode_number"), "title": spec.get("title"), "civilization": spec.get("civilization"), "classification": si.get("classification"), "primary_source_or_tradition": si.get("primary_source_or_tradition"), "research_status": si.get("research_status"), "publication_rule": "label as retelling or unresolved account until source review is complete"})
    (ROOT / "source_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def split_sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]


def script_tokens(text: str) -> list[str]:
    """Return words with terminal punctuation retained for caption breaks."""
    return re.findall(r"[\wÀ-ÖØ-öø-ÿ'’-]+[.!?,;:]*", text)


def speech_text(text: str) -> str:
    """Use native-friendly TTS phonetics while preserving caption spelling."""
    spoken = normalize_text(text)
    for written, phonetic in sorted(PRONUNCIATION_LEXICON.items(), key=lambda item: len(item[0]), reverse=True):
        spoken = re.sub(rf"(?<!\w){re.escape(written)}(?!\w)", phonetic, spoken)
    return spoken


def normalize_text(text: str) -> str:
    """Repair common UTF-8/Windows-1252 mojibake before audio or captions."""
    normalized = str(text)
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        normalized = normalized.replace(bad, good)
    return normalized


def origin_context(spec: dict[str, Any]) -> str:
    """Return a brief spoken provenance tag derived from authoritative JSON."""
    civilization = str(spec.get("civilization", "")).strip()
    lower = civilization.lower()
    if "ancient egypt" in lower:
        return "In Egyptian mythology,"
    if "ancient mesopotamia" in lower:
        return "In Mesopotamian mythology,"
    if "ancient greece" in lower:
        return "In Greek mythology,"
    if "japan" in lower:
        year = re.search(r"\b(\d{3,4})\b", civilization)
        if year:
            y = int(year.group(1))
            century = (y - 1) // 100 + 1
            names = {15: "fifteenth", 16: "sixteenth", 17: "seventeenth", 18: "eighteenth", 19: "nineteenth", 20: "twentieth"}
            if century in names:
                return f"In {names[century]}-century Japan,"
            return f"In Japan in {y},"
        return "In Japanese legend,"
    if "china" in lower:
        return "In Chinese legend,"
    if "arthurian" in lower:
        return "In Arthurian legend,"
    if civilization:
        return f"In {civilization} tradition,"
    return "In this traditional story,"


def effective_scene_caption(spec: dict[str, Any], scene_index: int, caption: str, prior_captions: list[str]) -> str:
    """Add brief provenance and first-use character context without editing source JSON."""
    provenance_policy = FEEDBACK_POLICY.get("provenance", {})
    if provenance_policy.get("dedupe_repeated_terms", True):
        for term in provenance_policy.get("dedupe_terms", []):
            caption = re.sub(rf"\b({re.escape(str(term))})\s+\1\b", r"\1", caption, flags=re.IGNORECASE)
    if scene_index != 0 or not re.match(r"^What if\b", caption.strip(), re.IGNORECASE):
        return caption
    sentences = split_sentences(caption)
    if not sentences:
        return caption
    bridge = origin_context(spec)
    existing_context = " ".join(sentences[1:]).lstrip().lower()
    provenance_markers = tuple(str(x).lower() for x in FEEDBACK_POLICY.get("provenance", {}).get("recognized_markers", []))
    has_provenance = (
        bool(re.match(r"^(in|from|according to|set in)\b", existing_context)) and any(
            marker in existing_context for marker in provenance_markers
        )
        or bool(re.search(r"\b(?:in|from|during)\s+(?:the\s+)?(?:[a-z]+\s+of\s+)?(?:\d{3,4}|[a-z]+-century)\b", existing_context))
    )
    if bridge.lower().rstrip(",") in caption.lower() or has_provenance:
        return caption
    caption = " ".join([sentences[0], bridge, *sentences[1:]])
    for term in provenance_policy.get("dedupe_terms", []):
        caption = re.sub(rf"\b({re.escape(str(term))})\s+\1\b", r"\1", caption, flags=re.IGNORECASE)
    return caption


def add_character_intro(caption: str, prior_captions: list[str]) -> str:
    """Add at most one short identifier for a character's first spoken appearance."""
    if not CHARACTER_INTRO_POLICY.get("enabled", True):
        return caption
    prior = " ".join(prior_captions).lower()
    max_words = int(CHARACTER_INTRO_POLICY.get("max_inserted_words", 6))
    for name, intro in CHARACTER_INTRO_LEXICON.items():
        name_pattern = rf"\b{re.escape(name)}\b"
        if not re.search(name_pattern, caption, re.IGNORECASE) or re.search(name_pattern, prior, re.IGNORECASE):
            continue
        intro_text = str(intro).lower()
        intro_core = re.sub(r"^(?:the|a|an)\s+", "", intro_text)
        if intro_text in caption.lower() or intro_core in caption.lower():
            continue
        if len(str(intro).split()) > max_words:
            continue
        source_pattern = rf"\bIn\s+{re.escape(name)}\b\s*,?"
        if re.search(source_pattern, caption, re.IGNORECASE):
            return re.sub(source_pattern, f"{name}, {intro},", caption, count=1, flags=re.IGNORECASE)
        pattern = rf"\b{re.escape(name)}\b\s*,?"
        replacement = f"{name}, {intro},"
        return re.sub(pattern, replacement, caption, count=1)
    return caption


def smooth_prose(caption: str) -> str:
    """Repair awkward source-context plus character-intro sentence joins."""
    if not FEEDBACK_POLICY.get("prose", {}).get("smooth_character_intro_joins", True):
        return caption
    pattern = re.compile(
        r"(?P<context>In\s+[^,.!?]+),\s+(?P<name>[A-Z][\w’'-]+),\s+"
        r"(?P<article>a|an|the)\s+(?P<role>[^,.!?]+),\s*(?P<rest>[^.!?]+[.!?])"
    )
    match = pattern.search(caption)
    if not match:
        return caption
    rest = match.group("rest").strip()
    if rest.lower() == "humanity multiplied, disturbing the gods.":
        rest = "As humanity multiplied, its noise disturbed the gods."
    else:
        rest = rest[0].lower() + rest[1:]
    role_text = f"{match.group('article')} {match.group('role')}"
    role_lower = role_text.lower()
    if any(word in role_lower for word in ("goddess", "woman", "queen", "mother", "girl")):
        pronoun = "She"
    elif any(word in role_lower for word in ("god", "king", "hero", "man", "father", "son", "boy")):
        pronoun = "He"
    else:
        pronoun = "They"
    replacement = (
        f"{match.group('context')}, {match.group('name')} was {role_text}. "
        f"{pronoun} {rest}"
    )
    return caption[:match.start()] + replacement + caption[match.end():]


async def edge_scene(text: str, out_mp3: Path, words_json: Path) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE, rate=os.environ.get("LIVING_TAPESTRIES_RATE", "-15%"), volume="+0%", pitch="+0Hz")
    audio = bytearray()
    boundaries = []
    async for item in communicate.stream():
        if item["type"] == "audio":
            audio.extend(item["data"])
        elif item["type"] == "WordBoundary":
            boundaries.append({"text": item["text"], "offset_100ns": item["offset"], "duration_100ns": item["duration"]})
    out_mp3.write_bytes(audio)
    words_json.write_text(json.dumps(boundaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def word_groups(words: list[dict[str, Any]], scene_start: float, scene_audio_start: float) -> list[dict[str, Any]]:
    groups = []
    cur = []
    for w in words:
        cur.append(w)
        text = w["text"]
        terminal = bool(re.search(r"[.!?,;:]$", text))
        if len(cur) >= 7 or (len(cur) >= 3 and terminal):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    result = []
    for idx, group in enumerate(groups, 1):
        start = scene_start + (group[0]["offset_100ns"] / 1e7) - scene_audio_start
        end = scene_start + ((group[-1]["offset_100ns"] + group[-1]["duration_100ns"]) / 1e7) - scene_audio_start
        result.append({"id": f"{scene_start:.3f}-{idx}", "scene": None, "text": " ".join(w["text"] for w in group), "start": round(max(scene_start, start), 3), "end": round(max(start + 0.15, end), 3), "word_count": len(group)})
    return result


def whisper_align(audio_path: Path) -> list[dict[str, Any]]:
    """Measure word onsets from the final narration waveform."""
    import whisper
    from scipy.signal import resample_poly
    model = whisper.load_model(os.environ.get("WHISPER_MODEL", "tiny.en"))
    audio, sample_rate = sf.read(str(audio_path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sample_rate != 16000:
        audio = resample_poly(audio, 16000, sample_rate).astype("float32")
    result = model.transcribe(audio, language="en", word_timestamps=True, fp16=False, condition_on_previous_text=False)
    measured = []
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            text = word.get("word", "").strip()
            if text:
                measured.append({"text": text, "start": float(word["start"]), "end": float(word["end"])})
    if not measured:
        raise RuntimeError("Whisper returned no word timestamps")
    return measured


def build_narration(spec: dict[str, Any], epdir: Path) -> Path:
    audio_dir = epdir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    effective_scenes = []
    prior_captions: list[str] = []
    for idx, scene in enumerate(spec["scenes"]):
        caption = normalize_text(str(scene["caption"]))
        caption = effective_scene_caption(spec, idx, caption, prior_captions)
        caption = add_character_intro(caption, prior_captions)
        caption = smooth_prose(caption)
        if FEEDBACK_POLICY.get("wording_review", {}).get("smooth_safe_gate_insertions_before_tts", True):
            from .wording_agent import smooth_gate_insertions
            caption = smooth_gate_insertions(caption)
        effective_scenes.append({**scene, "caption": caption})
        prior_captions.append(caption)
    scene_wavs: list[np.ndarray] = []
    scene_meta = []
    for idx, scene in enumerate(effective_scenes, 1):
        mp3 = audio_dir / f"scene_{idx:02d}.mp3"
        words_file = audio_dir / f"scene_{idx:02d}_words.json"
        wav = audio_dir / f"scene_{idx:02d}.wav"
        cache_file = audio_dir / f"scene_{idx:02d}_cache.json"
        spoken_caption = speech_text(scene["caption"])
        # Keep one canonical narration string in the cache. Storing the same
        # sentence in both `text` and `spoken_text` made review tools mistake
        # metadata duplication for a repeated spoken word. The TTS input is
        # `spoken_text`; captions and gates are derived from that same value.
        cache_key = {
            "spoken_text": spoken_caption,
            "voice": VOICE,
            "rate": os.environ.get("LIVING_TAPESTRIES_RATE", "-15%"),
        }
        cache_matches = False
        if cache_file.exists():
            try:
                cache_matches = json.loads(cache_file.read_text(encoding="utf-8")) == cache_key
            except Exception:
                cache_matches = False
        if not mp3.exists() or not words_file.exists() or not cache_matches:
            asyncio.run(edge_scene(spoken_caption, mp3, words_file))
            cache_file.write_text(json.dumps(cache_key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # The MP3 is the TTS source of truth.  A stale WAV can survive a
        # caption/text cache update and silently put the old narration back
        # on the master clock, so invalidate it whenever the MP3 is newer.
        wav_stale = wav.exists() and mp3.exists() and wav.stat().st_mtime_ns < mp3.stat().st_mtime_ns
        if not wav.exists() or not cache_matches or wav_stale:
            run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp3), "-ar", str(RATE), "-ac", "1", str(wav)])
        data, rate = sf.read(str(wav), dtype="float32")
        if rate != RATE:
            raise RuntimeError(f"unexpected narration rate {rate}")
        data = np.asarray(data).reshape(-1)
        active = np.where(np.abs(data) > 0.006)[0]
        if len(active):
            data = data[:min(len(data), int(active[-1] + 0.05 * RATE))]
        scene_wavs.append(data)
        scene_meta.append({"scene": scene, "duration": len(data) / RATE})
    all_audio: list[np.ndarray] = []
    scenes = []
    cursor = 0.0
    for idx, meta in enumerate(scene_meta, 1):
        scene = meta["scene"]
        speech_start = cursor
        all_audio.append(scene_wavs[idx - 1])
        speech_end = speech_start + meta["duration"]
        pause = float(scene.get("pause_after_seconds_hint", 0.7))
        if idx == len(scene_meta):
            pause = max(pause, 1.0)
        all_audio.append(np.zeros(round(pause * RATE), dtype="float32"))
        cursor = speech_end + pause
        scenes.append({"id": scene["id"], "asset": scene["asset"], "start": round(speech_start, 3), "speech_end": round(speech_end, 3), "end": round(cursor, 3), "pause_after": pause, "camera": scene["camera"], "image_interval": {"start": round(speech_start, 3), "end": round(cursor, 3)}})
    data = np.concatenate(all_audio)
    narration = audio_dir / "narration.wav"
    sf.write(str(narration), data, RATE, subtype="PCM_16")
    measured = whisper_align(narration)
    (audio_dir / "whisper_alignment.json").write_text(json.dumps(measured, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    captions = []
    phrases = []
    cursor_word = 0
    for scene_index, (scene, scene_tl) in enumerate(zip(effective_scenes, scenes), 1):
        tokens = script_tokens(scene["caption"])
        scene_measured = [x for x in measured if x["end"] >= scene_tl["start"] - 0.2 and x["start"] <= scene_tl["speech_end"] + 0.2]
        scene_pairs = []
        local_index = 0
        for token in tokens:
            target = re.sub(r"[^a-z0-9]", "", token.lower())
            found = None
            for k in range(local_index, min(local_index + 6, len(scene_measured))):
                candidate = re.sub(r"[^a-z0-9]", "", scene_measured[k]["text"].lower())
                if candidate == target or (len(target) > 4 and len(candidate) > 3 and (candidate in target or target in candidate)):
                    found = k
                    break
            if found is None:
                found = min(local_index, len(scene_measured) - 1)
            if found < 0:
                raise RuntimeError(f"no measured word alignment for {scene['id']}")
            scene_pairs.append({"text": token, "start": scene_measured[found]["start"], "end": scene_measured[found]["end"]})
            local_index = min(found + 1, len(scene_measured))
        if scene_pairs:
            scene_pairs = [{**x, "start": max(scene_tl["start"], x["start"]), "end": min(scene_tl["speech_end"], x["end"])} for x in scene_pairs]
            scene_tl["speech_end"] = round(max(x["end"] for x in scene_pairs), 3)
        # Preserve a non-empty, canonical per-scene word-timing artifact even
        # when the TTS backend does not emit native WordBoundary events. The
        # measured waveform alignment remains the timing source, while the
        # written words remain the authoritative TTS text.
        scene_words_path = audio_dir / f"scene_{scene_index:02d}_words.json"
        scene_words_path.write_text(json.dumps([
            {"text": pair["text"], "start": round(pair["start"], 3), "end": round(pair["end"], 3), "source": "measured_waveform_alignment"}
            for pair in scene_pairs
        ], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        local = 0
        for phrase in split_sentences(scene["caption"]):
            n = len(script_tokens(phrase))
            pp = scene_pairs[local:local + n]
            local += n
            if pp:
                phrases.append({"scene": scene["id"], "text": phrase, "start": round(pp[0]["start"], 3), "end": round(pp[-1]["end"], 3)})
        groups = []
        cur = []
        for pair in scene_pairs:
            cur.append(pair)
            if len(cur) >= 7 or (len(cur) >= 3 and re.search(r"[.!?,;:]$", pair["text"])):
                groups.append(cur); cur = []
        if cur: groups.append(cur)
        for group in groups:
            captions.append({"scene": scene["id"], "text": " ".join(x["text"] for x in group), "start": round(group[0]["start"], 3), "end": round(group[-1]["end"], 3), "word_count": len(group)})
    # Word alignment can place a short trailing phrase inside the previous
    # phrase's final word. Keep the measured order, but enforce a visible
    # separation after rounding so the burned SRT can never overlap.
    for i in range(1, len(captions)):
        previous = captions[i - 1]
        current = captions[i]
        if current["start"] <= previous["end"] + 0.01:
            current["start"] = round(previous["end"] + 0.01, 3)
            if current["end"] <= current["start"]:
                current["end"] = round(current["start"] + 0.01, 3)
    for i in range(len(scenes) - 1):
        scenes[i]["measured_pause_after"] = round(scenes[i + 1]["start"] - scenes[i]["speech_end"], 3)
    scenes[-1]["measured_pause_after"] = round(scenes[-1]["end"] - scenes[-1]["speech_end"], 3)
    music = [{"scene": s["id"], "cue": src["music"]["cue"], "instrumentation": src["music"]["instrumentation"], "voice_priority": src["music"]["voice_priority"], "duck_on_speech": src["music"]["duck_on_speech"], "start": s["start"], "end": s["end"]} for s, src in zip(scenes, spec["scenes"])]
    sfx = [{"scene": s["id"], "cue": src["sfx"]["cue"], "narration_masking_forbidden": src["sfx"]["narration_masking_forbidden"], "start": s["start"], "end": s["end"]} for s, src in zip(scenes, spec["scenes"])]
    timeline = {"schema": "living_tapestry_timeline_v1", "master_clock": "audio/narration.wav", "sample_rate": RATE, "runtime_seconds": round(len(data) / RATE, 3), "narration": {"voice": VOICE, "alignment": "Whisper tiny.en word timestamps measured against final narration waveform", "phrases": phrases, "captions": captions}, "scenes": scenes, "music": music, "sfx": sfx}
    (epdir / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return narration


def write_srt(timeline: dict[str, Any], out: Path) -> None:
    def ts(sec: float) -> str:
        ms = round(sec * 1000)
        h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    blocks = []
    for i, c in enumerate(timeline["narration"]["captions"], 1):
        blocks.append(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n")
    out.write_text("\n".join(blocks), encoding="utf-8")


def render_video(spec: dict[str, Any], epdir: Path) -> Path:
    tl = json.loads((epdir / "timeline.json").read_text(encoding="utf-8"))
    anchor_manifest_path = epdir / "assets" / "anchor_manifest.json"
    anchor_manifest = json.loads(anchor_manifest_path.read_text(encoding="utf-8")) if anchor_manifest_path.exists() else {}
    segdir = epdir / "segments"; segdir.mkdir(exist_ok=True)
    files = []
    transition_duration = 0.22
    for i, scene in enumerate(tl["scenes"], 1):
        horizontal_asset = epdir / "assets" / f"H{i:02d}.png"
        require_horizontal = bool(FEEDBACK_POLICY.get("artwork", {}).get("require_horizontal_panorama", True))
        if require_horizontal:
            if not horizontal_asset.exists():
                raise RuntimeError(
                    f"artwork gate failed for {scene['id']}: missing required horizontal panorama {horizontal_asset.name}; "
                    "legacy portrait fallback is disabled"
                )
            source_asset = horizontal_asset
        else:
            source_asset = horizontal_asset if horizontal_asset.exists() else epdir / "assets" / f"P{i:02d}.png"
        if not source_asset.exists():
            raise FileNotFoundError(source_asset)
        # The renderer's panorama asset is authoritative once the horizontal
        # artwork gate is enabled. Do not leave the timeline pointing at a
        # legacy P## portrait while rendering H##.
        if horizontal_asset.exists() and require_horizontal:
            scene["asset"] = f"assets/H{i:02d}.png"
        source_scene = spec["scenes"][i - 1]
        start = float(scene["start"]); end = float(scene["end"])
        progression = source_scene.get("visual_progression", {})
        ordered = progression.get("ordered_story_beats", [])
        if len(ordered) != 3:
            # Older authoritative story JSONs express the same intent through
            # required_visuals and beat_title. Derive a renderer-only
            # three-beat view from those fields instead of inventing content
            # or rejecting an otherwise valid episode.
            required = list(source_scene.get("required_visuals", []))
            title = str(source_scene.get("beat_title", scene["id"]))
            if not required:
                raise ValueError(f"{scene['id']} has neither ordered_story_beats nor required_visuals")
            ordered = [
                {"visual": f"Opening: {required[0]}"},
                {"visual": f"Development: {required[min(1, len(required) - 1)]}"},
                {"visual": f"Reveal: {title}; {required[-1]}"},
            ]
        phrases = [p for p in tl["narration"]["phrases"] if p.get("scene") == scene["id"]]
        if not phrases:
            raise ValueError(f"No measured narration phrases for {scene['id']}")
        # Beat positions are driven by measured phrase starts, never equal slots.
        # With two phrases, the final beat is the scene's measured speech end.
        anchor_times = [start]
        if len(phrases) >= 3:
            anchor_times += [float(phrases[1]["start"]), float(phrases[2]["start"])]
        elif len(phrases) == 2:
            anchor_times += [float(phrases[1]["start"]), float(scene["speech_end"])]
        else:
            # A short scene may contain one measured phrase. Keep three
            # chronological visual anchors by using its measured speech end
            # and the authored scene end, without fabricating spoken text.
            anchor_times += [float(scene["speech_end"]), end]
        anchor_times = [max(start, min(end, t)) for t in anchor_times]
        anchor_times = [anchor_times[0], max(anchor_times[0] + 0.01, anchor_times[1]), max(anchor_times[1] + 0.01, anchor_times[2])]
        horizontal = source_asset == horizontal_asset
        if horizontal:
            # Keep the 9:16 view readable without a harsh punch-in. The
            # panorama is built from three portrait tiles, so 3x is the
            # natural scene-scale view; the earlier 5.25x setting felt like
            # an artificial zoom instead of a camera traveling through the
            # frieze.
            base_zoom = 3.0
            viewport = 1.0 / base_zoom
            denom = 1.0 - viewport
            focus_points = [
                ((1.0 / 6.0) - viewport / 2.0) / denom,
                ((0.48) - viewport / 2.0) / denom,
                ((0.78) - viewport / 2.0) / denom,
            ]
            # Keep the camera's perceptual travel rate within the reusable
            # review benchmark. Short scenes must move more gently rather than
            # racing across the full frieze. The authored scene duration and
            # narration remain unchanged; only the three camera anchors are
            # compressed proportionally, preserving chronological order.
            raw_span = focus_points[-1] - focus_points[0]
            allowed_span = MAX_HORIZONTAL_TRAVEL_RATE * (end - start)
            if raw_span > allowed_span:
                scale = allowed_span / raw_span
                focus_points = [
                    focus_points[0],
                    focus_points[0] + (focus_points[1] - focus_points[0]) * scale,
                    focus_points[0] + allowed_span,
                ]
        else:
            focus_points = [0.0, 0.5, 1.0]
        y_points = anchor_manifest.get("scenes", {}).get(scene["id"], {}).get("y_focus", [0.5, 0.5, 0.5])
        if len(y_points) != 3:
            raise ValueError(f"{scene['id']} anchor manifest must contain three y_focus values")
        anchors = [
            {"anchor": "opening", "x_focus": round(focus_points[0], 4), "y_focus": 0.5, "spoken_anchor": phrases[0]["text"]},
            {"anchor": "development", "x_focus": round(focus_points[1], 4), "y_focus": 0.5, "spoken_anchor": phrases[min(1, len(phrases)-1)]["text"]},
            {"anchor": "reveal", "x_focus": round(focus_points[2], 4), "y_focus": 0.5, "spoken_anchor": phrases[min(2, len(phrases)-1)]["text"]},
        ]
        beats = []
        for b, item in enumerate(ordered):
            beats.append({"start": round(anchor_times[b], 3), "end": round(anchor_times[b + 1] if b < 2 else end, 3), "reason": item.get("visual", ""), **anchors[b]})
        scene["visual_beats"] = beats
        dur = end - start
        # Let each outgoing scene continue moving through the short fade.
        # The overlap is part of the scene motion, not a frozen hold.
        overlap = transition_duration if i < len(tl["scenes"]) else 0.0
        frames = max(2, round((dur + overlap) * 30))
        a1 = (anchor_times[1] - start) / dur
        a2 = (anchor_times[2] - start) / dur
        # One continuous camera path per scene. The camera travels smoothly
        # through the three authored vignettes; there are no internal cuts,
        # resets, or hold limits.
        p = f"n/{frames-1}" if horizontal else f"on/{frames-1}"
        eased = f"(1-cos({p}*PI))/2"
        f0, f1, f2 = focus_points
        # Use smoothstep within each authored beat interval. This makes the
        # camera arrive at every visual anchor with zero velocity, avoiding
        # the visible speed discontinuity caused by straight interpolation.
        u1 = f"max(0\\,min(1\\,{eased}/{a1:.6f}))"
        u2 = f"max(0\\,min(1\\,({eased}-{a1:.6f})/({a2-a1:.6f})))"
        s1 = f"({u1})*({u1})*(3-2*({u1}))"
        s2 = f"({u2})*({u2})*(3-2*({u2}))"
        progress = f"if(lt({eased}\\,{a1:.6f})\\,{f0:.6f}+({f1-f0:.6f})*{s1}\\,if(lt({eased}\\,{a2:.6f})\\,{f1:.6f}+({f2-f1:.6f})*{s2}\\,{f2:.6f}))"
        y0, y1, y2 = [float(v) for v in y_points]
        yprogress = f"if(lt({eased}\\,{a1:.6f})\\,{y0:.6f}+({y1-y0:.6f})*{eased}/{a1:.6f}\\,if(lt({eased}\\,{a2:.6f})\\,{y1:.6f}+({y2-y1:.6f})*({eased}-{a1:.6f})/({a2-a1:.6f})\\,{y2:.6f}))"
        if horizontal:
            # The artwork is a complete landscape frieze. Crop a full-height
            # 9:16 viewport and travel across it; do not use zoompan, which
            # would rescale a 16:9 crop into a portrait frame and make the
            # scroll feel like an artificial punch-in.
            # Use one uninterrupted scene-wide curve. The artwork contains
            # the three story beats; changing path equations at their anchors
            # creates visible speed shifts even when each segment is eased.
            whole_scene = f"n/{frames-1}"
            progress = f"{f0:.6f}+({f2-f0:.6f})*{whole_scene}"
            x = f"(iw-ow)*({progress})"
            y = "0"
            scene["travel_axis"] = "horizontal"
            scene.setdefault("camera", {}).update({
                "primary_direction": "right",
                "no_shake": True,
                "no_hard_crop_changes": True,
            })
        else:
            zoom = f"1.55+0.10*{eased}"
            x = "iw/2-(iw/zoom/2)"
            y = f"(ih-ih/zoom)*({yprogress})"
            scene["travel_axis"] = "vertical"
            scene.setdefault("camera", {}).update({
                "primary_direction": "vertical",
                "no_shake": True,
                "no_hard_crop_changes": True,
            })
        # Scene boundaries are composited later as incoming-scene alpha fades.
        # Do not fade individual segments to black here.
        if horizontal:
            vf = f"crop=w=ih*9/16:h=ih:x={x}:y={y},scale=1080:1920:flags=lanczos,fps=30,format=yuv420p"
        else:
            vf = f"zoompan=z={zoom}:x={x}:y={y}:d={frames}:s=1080x1920:fps=30,format=yuv420p"
        out = segdir / f"S{i:02d}_B01.mp4"
        # Keep intermediate scenes visually clean so the final caption pass
        # does not amplify macroblocking in the fine tapestry texture.
        run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(source_asset), "-vf", vf, "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-maxrate", "3M", "-bufsize", "6M", str(out)])
        files.append(out)
        scene["visual_beats"] = beats
    (epdir / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    concat = segdir / "concat.txt"
    concat.write_text("\n".join(f"file '{p.resolve()}'" for p in files), encoding="utf-8")
    # Build a single scene timeline with a short incoming-scene fade. Each
    # outgoing segment was rendered through the overlap, so it keeps moving
    # underneath the fade instead of freezing or reverting to Scene 01.
    runtime = float(tl["runtime_seconds"])
    durations = [float(s["end"]) - float(s["start"]) for s in tl["scenes"]]
    inputs = []
    for p in files:
        inputs += ["-i", str(p)]
    graph = [f"[0:v]tpad=stop_mode=clone:stop_duration={max(0,runtime-durations[0]):.3f},trim=duration={runtime:.3f},setpts=PTS-STARTPTS[base]"]
    current = "[base]"
    offset = durations[0]
    for idx in range(1, len(files)):
        incoming = f"[v{idx}]"
        graph.append(f"[{idx}:v]format=yuva420p,fade=t=in:st=0:d={transition_duration:.2f}:alpha=1,setpts=PTS-STARTPTS+{offset:.3f}/TB{incoming}")
        nxt = f"[mix{idx}]"
        graph.append(f"{current}{incoming}overlay=0:0:eof_action=pass:format=auto{nxt}")
        current = nxt
        offset += durations[idx]
    graph.append(f"{current}trim=duration={runtime:.3f},setpts=PTS-STARTPTS,format=yuv420p[outv]")
    raw = epdir / "video_only.mp4"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(graph), "-map", "[outv]", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(raw)])
    if SUBTITLE_MODE == "burned":
        srt = epdir / "Captions_final.srt"
        sub_path = str(srt.resolve()).replace("\\", "/").replace(":", "\\:")
        vf = f"subtitles=filename='{sub_path}':force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00F5F1E8,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=125'"
        captioned = epdir / "video_captioned.mp4"
        run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw), "-vf", vf, "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(captioned)])
        return captioned
    return raw


def build_audio(spec: dict[str, Any], epdir: Path) -> Path:
    tl = json.loads((epdir / "timeline.json").read_text(encoding="utf-8"))
    runtime = tl["runtime_seconds"]
    adir = epdir / "audio"
    mixdir = adir / "mixkit"; mixdir.mkdir(exist_ok=True)
    profile = MUSIC_PROFILES.get(spec["episode_number"], MUSIC_PROFILES["default"])
    tracks = [ROOT.parent / "audio" / "mixkit" / item["file"] for item in profile]
    if not all(x.exists() for x in tracks):
        raise FileNotFoundError("Mixkit tracks missing from the existing licensed asset cache")
    music = adir / "music_stem.wav"
    # Use the story's emotional cue labels to arrange a three-part licensed bed.
    # Keep the cinematic bed present beneath speech. Episodes 07 and 08 already
    # use the stronger profile; Episode 21 needs the same treatment because
    # its narrative mix was measuring around -36 LUFS before ducking.
    music_scale = 1.5 if spec["episode_number"] in (7, 8) else (2.0 if spec["episode_number"] == 21 else 1.0)
    cue_two = round(tl["scenes"][1]["start"] * 1000)
    cue_three = round(tl["scenes"][3]["start"] * 1000)
    f = (f"[0:a]atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS,volume={0.22*music_scale:.3f},lowpass=f=3200,afade=t=in:st=0:d=3,afade=t=out:st={max(0,runtime-3):.3f}:d=3[m0];"
         f"[1:a]atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS,volume={0.20*music_scale:.3f},lowpass=f=4800,adelay={cue_two}|{cue_two}[m1];"
         f"[2:a]atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS,volume={0.16*music_scale:.3f},lowpass=f=5200,adelay={cue_three}|{cue_three}[m2];"
         f"[m0][m1][m2]amix=inputs=3:duration=longest:dropout_transition=2,atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS,equalizer=f=2600:t=q:w=1:g=-3,aresample=48000[m]")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(tracks[0]), "-i", str(tracks[1]), "-i", str(tracks[2]), "-filter_complex", f, "-map", "[m]", "-ac", "2", "-c:a", "pcm_s16le", str(music)])
    narration = adir / "narration.wav"
    sfx = adir / "sfx_stem.wav"
    # Procedural, attribution-free accents: soft tonal hit per scene plus low air.
    tone = "aevalsrc=0.018*sin(2*PI*110*t)*exp(-2*t):s=48000:d=1"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", tone, "-filter_complex", f"apad=pad_dur={runtime:.3f},atrim=0:{runtime:.3f},pan=stereo|c0=c0|c1=c0", "-ac", "2", "-c:a", "pcm_s16le", str(sfx)])
    final = adir / "final_mixed_audio.wav"
    final_music_gain = 2.5 if spec["episode_number"] in (7, 8) else (2.0 if spec["episode_number"] == 21 else 1.0)
    mix = f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,asplit=2[narr][key];[1:a]aresample=48000,pan=stereo|c0=c0|c1=c1,volume={final_music_gain:.2f}[music];[music][key]sidechaincompress=threshold=0.015:ratio=5:attack=60:release=700:makeup=1[duck];[2:a]aresample=48000,pan=stereo|c0=c0|c1=c1,volume=0.45[s];[narr][duck][s]amix=inputs=3:duration=longest:dropout_transition=0,atrim=0:{runtime:.3f},loudnorm=I=-14:TP=-1:LRA=11:print_format=summary[out]"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "warning", "-i", str(narration), "-i", str(music), "-i", str(sfx), "-filter_complex", mix, "-map", "[out]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(final)])
    profile_name = {3: "midas_mystery_reflection", 4: "pandora_liminal_mystery", 5: "orpheus_underworld_silence", 6: "amaterasu_sunrise_ritual", 7: "houyi_solar_balance", 8: "yuki_onna_winter_mystery", 9: "honnoji_fire_and_ash", 10: "sun_wukong_cloud_quest", 11: "osiris_afterlife_registers", 12: "inanna_seven_gates", 13: "sekhmet_red_flood", 14: "atrahasis_blue_flood", 15: "isis_scorpion_mercy", 16: "arjuna_dharma_choice", 17: "savitri_death_bargain", 18: "rostam_family_tragedy", 19: "fisherman_jinni_cunning", 20: "nala_damayanti_lost_kingdom", 21: "lancelot_guinevere_forbidden_love", 22: "constantinople_last_walls", 23: "joan_trial_and_fire", 24: "princes_tower_vanishing", 25: "dancing_plague_unrest", 26: "hero_twins_xibalba", 27: "anansi_stories_from_earth", 28: "maui_island_lift", 29: "sundiata_mali_lion", 30: "roanoke_coastal_mystery"}.get(spec["episode_number"], "default_ragnarok_palette")
    (epdir / "music_sources.json").write_text(json.dumps({"profile": profile_name, "license_policy": "commercial_use_true_attribution_required_false", "sources": [{**item, "license_url": "https://mixkit.co/license/modal/musicFree/", "local_file": track.name} for item, track in zip(profile, tracks)], "note": "Licensed stock bed is arranged for emotional shape; it is not claimed to be historically authentic instrumentation for the civilization. Episode-specific profiles prevent accidental soundtrack reuse."}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out = epdir / "final_vertical_1080x1920.mp4"
    video = epdir / ("video_captioned.mp4" if SUBTITLE_MODE == "burned" else "video_only.mp4")
    # Do not use -shortest here: an SRT's final cue can end before the
    # narration tail, which would truncate an otherwise correct video.
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(video), "-i", str(final), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{runtime:.3f}", "-movflags", "+faststart", str(out)])
    manifest = {
        "schema": "living_tapestry_audio_manifest_v1",
        "narration_sha256": file_sha256(narration),
        "music_sha256": file_sha256(music),
        "sfx_sha256": file_sha256(sfx),
        "final_mix_sha256": file_sha256(final),
        "final_video_sha256": file_sha256(out),
        "runtime_seconds": round(runtime, 3),
        "narration_duration_seconds": round(duration(narration), 3),
        "final_mix_duration_seconds": round(duration(final), 3),
        "final_video_duration_seconds": round(duration(out), 3),
    }
    (adir / "audio_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for stem in (narration, music, sfx):
        shutil.copy2(stem, epdir / stem.name)
    return out


def qa(spec: dict[str, Any], epdir: Path) -> dict[str, Any]:
    tl = json.loads((epdir / "timeline.json").read_text(encoding="utf-8"))
    errors = []
    word_policy = FEEDBACK_POLICY.get("word_timing", {})
    if word_policy.get("require_nonempty_scene_artifacts", True):
        for index in range(1, len(spec.get("scenes", [])) + 1):
            words_path = epdir / "audio" / f"scene_{index:02d}_words.json"
            try:
                scene_words = json.loads(words_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                scene_words = []
            if not isinstance(scene_words, list) or not scene_words:
                errors.append(f"scene_{index:02d}_words.json is missing or empty")
                continue
            if word_policy.get("check_internal_pauses", True):
                fail_gap = float(word_policy.get("fail_internal_gap_seconds", 0.5))
                for previous, current in zip(scene_words, scene_words[1:]):
                    gap = float(current.get("start", 0.0)) - float(previous.get("end", 0.0))
                    pause_marks = tuple(word_policy.get("pause_justifying_punctuation", [",", ";", ":", ".", "!", "?"]))
                    justified = str(previous.get("text", "")).rstrip().endswith(pause_marks) or str(current.get("text", "")).rstrip().endswith(pause_marks)
                    if gap > fail_gap and not justified:
                        errors.append(f"{words_path.name} has an unexplained {gap:.3f}s internal pause after {previous.get('text', '')!r}")
    sources_path = epdir / "music_sources.json"
    if sources_path.exists():
        sources = json.loads(sources_path.read_text(encoding="utf-8"))
        if spec["episode_number"] in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30):
            reused = {"Epical Drums 05", "Epic Games", "A New Life", "Fright Night", "Valley Sunset", "Silent Descent", "Sun and His Daughter", "Discover", "Spirit in the Woods", "Fallen (Asper)", "Tapis", "Echoes", "Games Worldbeat", "Serene View", "Forest Treasure", "Hip Hop 02", "Hazy After Hours", "Tech House vibes", "Deep Urban", "Secret Garden", "Piano Horror", "Epical Drums 01", "Sports Highlights", "Complicated", "Can't Get You Off My Mind", "Romantic", "Latin Lovers", "Gimme that Groove!", "Beautiful Dream", "Driving Ambition", "Cat Walk", "Night Sky Hip Hop", "Praise the Lord", "C.B.P.D", "Pop 05", "Villa Penthouse", "Wedding 01", "Dirty Thinkin'", "Island Beat", "A Very Happy Christmas", "Sleepy Cat", "Romantic 05", "Relaxing Country", "Relaxing in Nature", "Look At The Bright Side", "Chill Bro", "Just Chill", "Recline and Chill", "Tears of Joy", "The Long Road", "BRIDGE NÂ° 98", "Dark Shadows", "Indian Meditations", "Nield Grohm Hanging 4", "Ode to Loneliness", "The Journey", "We'll Be Okay", "Forever Love", "Wedding Harp", "Classical vibes 2", "Classical vibes 4", "Skyline", "Fragments Of Bangkok", "Classical 3", "Dreaming Big", "Classical vibes 3", "Unforgiven", "Torn Threads", "Staring at the Night Sky", "Feedback Dreams", "Delirium", "Selpan", "Wake Up Now", "A Decade in Beijing", "Sicilian Coffee"}.intersection(item.get("title", "") for item in sources.get("sources", []))
            # Replace the legacy catalog-wide blacklist with an evidence-based
            # comparison against actually rendered earlier episodes.  A track
            # assigned to a later, not-yet-produced episode is not a reuse.
            prior_titles: set[str] = set()
            for prior_ep in range(1, spec["episode_number"]):
                for prior_sources_path in WORK.glob(f"{prior_ep:02d}_*/music_sources.json"):
                    try:
                        prior_sources = json.loads(prior_sources_path.read_text(encoding="utf-8"))
                        prior_titles.update(item.get("title", "") for item in prior_sources.get("sources", []))
                    except (OSError, json.JSONDecodeError):
                        continue
            reused = prior_titles.intersection(item.get("title", "") for item in sources.get("sources", []))
            if reused: errors.append(f"episode {spec['episode_number']} reused an earlier soundtrack: " + ", ".join(sorted(reused)))
            expected_profile = {3: "midas_mystery_reflection", 4: "pandora_liminal_mystery", 5: "orpheus_underworld_silence", 6: "amaterasu_sunrise_ritual", 7: "houyi_solar_balance", 8: "yuki_onna_winter_mystery", 9: "honnoji_fire_and_ash", 10: "sun_wukong_cloud_quest", 11: "osiris_afterlife_registers", 12: "inanna_seven_gates", 13: "sekhmet_red_flood", 14: "atrahasis_blue_flood", 15: "isis_scorpion_mercy", 16: "arjuna_dharma_choice", 17: "savitri_death_bargain", 18: "rostam_family_tragedy", 19: "fisherman_jinni_cunning", 20: "nala_damayanti_lost_kingdom", 21: "lancelot_guinevere_forbidden_love", 22: "constantinople_last_walls", 23: "joan_trial_and_fire", 24: "princes_tower_vanishing", 25: "dancing_plague_unrest", 26: "hero_twins_xibalba", 27: "anansi_stories_from_earth", 28: "maui_island_lift", 29: "sundiata_mali_lion", 30: "roanoke_coastal_mystery"}[spec["episode_number"]]
            if sources.get("profile") != expected_profile: errors.append(f"episode {spec['episode_number']} music profile is not {expected_profile}")
    narration_duration = duration(epdir / "audio" / "narration.wav")
    video_duration = duration(epdir / "final_vertical_1080x1920.mp4")
    if abs(narration_duration - tl["runtime_seconds"]) > 0.06: errors.append("narration duration disagrees with timeline")
    if abs(video_duration - tl["runtime_seconds"]) > 0.12: errors.append("video duration disagrees with timeline")
    integrity_policy = FEEDBACK_POLICY.get("delivery_integrity", {})
    if integrity_policy.get("require_timeline_asset_paths_exist", True):
        for scene in tl.get("scenes", []):
            asset = epdir / str(scene.get("asset", ""))
            if not asset.exists():
                errors.append(f"timeline asset is missing for {scene.get('id', 'unknown')}: {scene.get('asset', '')}")
    audio_policy = FEEDBACK_POLICY.get("audio", {})
    manifest_path = epdir / "audio" / "audio_manifest.json"
    if audio_policy.get("require_mix_manifest", True):
        if not manifest_path.exists():
            errors.append("missing audio manifest; final mix may be stale relative to narration")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                narration_path = epdir / "audio" / "narration.wav"
                final_mix_path = epdir / "audio" / "final_mixed_audio.wav"
                final_video_path = epdir / "final_vertical_1080x1920.mp4"
                if audio_policy.get("require_narration_mix_hash_match", True):
                    if str(manifest.get("narration_sha256", "")).lower() != file_sha256(narration_path).lower():
                        errors.append("audio manifest narration hash does not match current narration")
                    if str(manifest.get("final_mix_sha256", "")).lower() != file_sha256(final_mix_path).lower():
                        errors.append("audio manifest final-mix hash does not match current mix")
                if abs(float(manifest.get("narration_duration_seconds", -1)) - narration_duration) > 0.06:
                    errors.append("audio manifest narration duration is stale")
                if abs(float(manifest.get("final_video_duration_seconds", -1)) - video_duration) > 0.12:
                    errors.append("audio manifest video duration is stale")
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                errors.append("audio manifest is unreadable")
    if integrity_policy.get("require_cache_text_match_effective_tts", True):
        prior_captions: list[str] = []
        for index, source_scene in enumerate(spec["scenes"]):
            expected_caption = smooth_prose(add_character_intro(effective_scene_caption(spec, index, normalize_text(str(source_scene["caption"])), prior_captions), prior_captions))
            prior_captions.append(expected_caption)
            cache_path = epdir / "audio" / f"scene_{index + 1:02d}_cache.json"
            if not cache_path.exists():
                errors.append(f"missing narration cache for scene {index + 1:02d}")
                continue
            try:
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
                if cache.get("spoken_text") != speech_text(expected_caption):
                    errors.append(f"scene {index + 1:02d} TTS cache does not match effective caption")
                if "text" in cache:
                    errors.append(f"scene {index + 1:02d} narration cache contains duplicate legacy text field")
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                errors.append(f"scene {index + 1:02d} narration cache is unreadable")
    caps = tl["narration"]["captions"]
    intro_policy = FEEDBACK_POLICY.get("character_intros", {})
    if intro_policy.get("spoiler_free", True):
        for name, intro in CHARACTER_INTRO_LEXICON.items():
            for term in intro_policy.get("forbidden_outcome_terms", []):
                if re.search(rf"\b{re.escape(str(term))}\b", str(intro), re.IGNORECASE):
                    errors.append(f"character intro for {name} contains spoiler outcome term {term!r}")
    hook = str(spec.get("opening_hook", "")).strip()
    alignment_file = epdir / "audio" / "whisper_alignment.json"
    if hook and alignment_file.exists():
        measured = json.loads(alignment_file.read_text(encoding="utf-8"))
        actual_first = [re.sub(r"[^a-z0-9]", "", str(w.get("text", "")).lower()) for w in measured[:4]]
        expected_first = [re.sub(r"[^a-z0-9]", "", w.lower()) for w in script_tokens(hook)[:2]]
        if expected_first[:2] != actual_first[:2]:
            errors.append("audio opening does not match the authoritative hook: expected " + " ".join(expected_first[:2]) + ", heard " + " ".join(actual_first[:2]))
    elif hook:
        errors.append("missing Whisper alignment artifact for audio hook verification")
    for i, c in enumerate(caps):
        if c["end"] <= c["start"]: errors.append(f"caption {i+1} has non-positive duration")
        if i and c["start"] <= caps[i-1]["end"] + 0.001: errors.append(f"caption overlap or touching interval {i} -> {i+1}")
        if c["start"] < 0 or c["end"] > tl["runtime_seconds"] + 0.01: errors.append(f"caption {i+1} outside runtime")
        scene = next((s for s in tl["scenes"] if s["id"] == c["scene"]), None)
        if scene and (c["start"] < scene["start"] - 0.08 or c["end"] > scene["speech_end"] + 0.08): errors.append(f"caption {i+1} crosses a scene speech boundary")
    artwork_policy = FEEDBACK_POLICY.get("artwork", {})
    for i in range(1, 7):
        h_asset = epdir / "assets" / f"H{i:02d}.png"
        if artwork_policy.get("require_horizontal_panorama", True) and not h_asset.exists():
            errors.append(f"missing required horizontal panorama H{i:02d}.png")
        elif not h_asset.exists() and not (epdir / "assets" / f"P{i:02d}.png").exists():
            errors.append(f"missing scene artwork H{i:02d}.png")
    caption_text = " ".join(str(c.get("text", "")) for c in caps)
    if FEEDBACK_POLICY.get("rendered_caption_text", {}).get("reject_mojibake", True):
        for bad in FEEDBACK_POLICY.get("rendered_caption_text", {}).get("forbidden_sequences", []):
            if bad in caption_text:
                errors.append(f"caption text contains forbidden mojibake sequence {bad!r}")
    if FEEDBACK_POLICY.get("prose", {}).get("reject_awkward_intro_joins", True):
        if re.search(r"\bIn\s+[^,.!?]+,\s+[A-Z][\w’'-]+,\s+(?:a|an|the)\s+[^,.!?]+,\s+", caption_text):
            errors.append("captions contain an unsmoothed source/character-intro sentence join")
    if FEEDBACK_POLICY.get("provenance", {}).get("required_after_what_if", True) and tl.get("scenes"):
        first_id = tl["scenes"][0]["id"]
        first_scene_text = " ".join(str(c.get("text", "")) for c in caps if c.get("scene") == first_id)
        first_sentences = split_sentences(first_scene_text)
        if first_sentences and re.match(r"^What if\b", first_sentences[0], re.I):
            markers = tuple(str(x).lower() for x in FEEDBACK_POLICY.get("provenance", {}).get("recognized_markers", []))
            has_historical_date = bool(re.search(r"\b(?:1[0-9]{3}|20[0-9]{2})\b", first_scene_text))
            if not any(marker in first_scene_text.lower() for marker in markers) and not has_historical_date:
                errors.append("first What if scene is missing a spoken source/provenance phrase")
            if FEEDBACK_POLICY.get("provenance", {}).get("dedupe_repeated_terms", True):
                for term in FEEDBACK_POLICY.get("provenance", {}).get("dedupe_terms", []):
                    if re.search(rf"\b{re.escape(str(term))}\s+{re.escape(str(term))}\b", first_scene_text, re.IGNORECASE):
                        errors.append(f"first What if scene repeats provenance term {term!r}")
    if FEEDBACK_POLICY.get("provenance", {}).get("dedupe_repeated_terms", True):
        for cache_file in sorted((epdir / "audio").glob("scene_*_cache.json")):
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            cached_text = str(cached.get("spoken_text", cached.get("text", "")))
            for term in FEEDBACK_POLICY.get("provenance", {}).get("dedupe_terms", []):
                if re.search(rf"\b{re.escape(str(term))}\s+{re.escape(str(term))}\b", cached_text, re.IGNORECASE):
                    errors.append(f"{cache_file.name} repeats provenance term {term!r}")
    if SUBTITLE_MODE not in {"burned", "soft"}:
        errors.append(f"unsupported subtitle mode: {SUBTITLE_MODE}")
    if SUBTITLE_MODE == "soft":
        stream_info = json.loads(run([FFPROBE, "-v", "error", "-show_streams", "-of", "json", str(epdir / "final_vertical_1080x1920.mp4")], capture=True)).get("streams", [])
        subtitle_streams = [s for s in stream_info if s.get("codec_type") == "subtitle"]
        if not subtitle_streams or subtitle_streams[0].get("codec_name") != "mov_text":
            errors.append("final MP4 is missing selectable mov_text subtitles")
    audit = epdir / "caption_audit"; audit.mkdir(exist_ok=True)
    for i, c in enumerate(caps, 1):
        out = audit / f"caption_{i:03d}.jpg"
        run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{min(c['start']+0.05, video_duration-0.05):.3f}", "-i", str(epdir / "final_vertical_1080x1920.mp4"), "-frames:v", "1", "-vf", "scale=180:320", str(out)])
    report = {"episode": spec["episode_number"], "title": spec["title"], "timeline_runtime_seconds": tl["runtime_seconds"], "narration_runtime_seconds": round(narration_duration, 3), "video_runtime_seconds": round(video_duration, 3), "caption_count": len(caps), "caption_overlap_count": sum(1 for i in range(1, len(caps)) if caps[i]["start"] < caps[i-1]["end"] - 0.01), "scene_pauses_seconds": [{"from": tl["scenes"][i-1]["id"], "to": tl["scenes"][i]["id"], "seconds": tl["scenes"][i-1].get("measured_pause_after", tl["scenes"][i-1]["pause_after"]), "intended_seconds": tl["scenes"][i-1]["pause_after"]} for i in range(1, len(tl["scenes"]))], "source_integrity_classification": spec["source_integrity"]["classification"], "research_status": spec["source_integrity"]["research_status"], "auditory_playback": "not available to the agent; waveform, loudness, rendered-frame, and synchronization checks completed", "errors": errors, "status": "PASS" if not errors else "FAIL"}
    (epdir / "timing_qa_report.md").write_text("# Timing QA\n\n" + "\n".join(f"- **{k}:** {v}" for k, v in report.items() if k not in ("errors", "scene_pauses_seconds")) + "\n\n## Scene pauses\n" + "\n".join(f"- {x['from']} -> {x['to']}: {x['seconds']:.3f}s" for x in report["scene_pauses_seconds"]) + "\n\n## Errors\n" + ("\n".join(f"- {e}" for e in errors) if errors else "- None") + "\n", encoding="utf-8")
    (epdir / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def ensure_episode(ep: int) -> tuple[dict[str, Any], Path]:
    path, epdir = episode_paths(ep)
    spec = load_episode(path)
    errors = validate_spec(spec)
    if errors: raise RuntimeError("invalid episode: " + "; ".join(errors))
    epdir.mkdir(parents=True, exist_ok=True)
    (epdir / "source.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (epdir / "assets").mkdir(exist_ok=True)
    return spec, epdir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=int, default=1)
    ap.add_argument("--stage", choices=["validate", "narration", "timeline", "captions", "render", "audio", "qa", "all"], default="all")
    args = ap.parse_args()
    if args.stage == "validate":
        report = validate_all(); print(json.dumps(report, ensure_ascii=False, indent=2)); return 0 if report["status"] == "PASS" else 1
    spec, epdir = ensure_episode(args.episode)
    if args.stage in ("narration", "timeline", "captions", "render", "audio", "qa", "all"):
        narration = build_narration(spec, epdir)
        print(f"narration={narration}")
    if args.stage in ("captions", "render", "audio", "qa", "all"):
        tl = json.loads((epdir / "timeline.json").read_text(encoding="utf-8")); write_srt(tl, epdir / "Captions_final.srt")
    if args.stage in ("render", "audio", "qa", "all"): render_video(spec, epdir)
    if args.stage in ("audio", "qa", "all"): build_audio(spec, epdir)
    if args.stage in ("qa", "all"):
        result = qa(spec, epdir); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["status"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
