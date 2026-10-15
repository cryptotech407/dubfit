import json
import pytest

from dubfit.timings import load_timings, parse_srt

SRT = """1
00:00:00,000 --> 00:00:12,500
first line

2
00:00:12,500 --> 00:00:30,000
second line

3
00:00:30,000 --> 00:00:41,250
third
"""


def test_parse_srt():
    s = parse_srt(SRT)
    assert [x.id for x in s] == ["1", "2", "3"]
    assert s[1].start == 12.5 and s[1].end == 30.0
    assert s[2].duration == pytest.approx(11.25)


def test_srt_accepts_a_dot_for_the_milliseconds():
    assert parse_srt(SRT.replace(",", "."))[0].end == 12.5


def test_srt_with_no_cues_is_an_error():
    with pytest.raises(ValueError):
        parse_srt("nothing here")


def test_json_list_shape(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps([{"id": "a", "start": 0, "end": 5},
                             {"id": "b", "start": 5, "end": 9}]))
    assert [x.id for x in load_timings(p)] == ["a", "b"]


def test_json_scenes_wrapper_shape(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"total": 9.0,
                             "scenes": [{"id": "a", "start": 0, "end": 5},
                                        {"id": "b", "start": 5, "end": 9}]}))
    assert load_timings(p)[1].end == 9.0


def test_json_id_to_pair_shape(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"e02": [5.0, 9.0], "e01": [0.0, 5.0]}))
    got = load_timings(p)
    assert [x.id for x in got] == ["e01", "e02"]   # sorted by start


def test_dur_key_is_accepted_in_place_of_end(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps([{"id": "a", "start": 2.0, "dur": 3.0}]))
    assert load_timings(p)[0].end == 5.0


def test_srt_file_is_detected_by_suffix(tmp_path):
    p = tmp_path / "t.srt"
    p.write_text(SRT)
    assert len(load_timings(p)) == 3
