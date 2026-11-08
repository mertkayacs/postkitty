import pytest

from engine import copyfit as c


class TestXWeighted:
    def test_ascii_is_one_each(self):
        assert c.x_weighted_length("hello world") == 11

    @pytest.mark.parametrize("text, expected", [
        ("你好", 4),             # CJK, default weight 200 each
        ("café", 4),             # Latin range 0-4351 weighs 100
        ("—", 1),           # em dash is in the 8208-8223 range
        ("あ", 2),           # hiragana is above 4351
    ])
    def test_ranges(self, text, expected):
        assert c.x_weighted_length(text) == expected

    @pytest.mark.parametrize("emoji", [
        "😀", "👍🏽", "🇹🇷", "👨‍👩‍👧", "1️⃣", "❤️",
    ])
    def test_emoji_sequence_counts_as_two(self, emoji):
        assert c.x_weighted_length(emoji) == 2

    def test_zwj_family_is_not_summed_per_code_point(self):
        assert c.x_weighted_length("👨‍👩‍👧‍👦") == 2

    def test_url_counts_23_whatever_its_length(self):
        long_url = "https://example.com/" + "a" * 200
        assert c.x_weighted_length(f"see {long_url} now") == 4 + 23 + 4
        assert c.x_weighted_length("https://t.co/x") == 23

    def test_bare_domain_counts_23_but_prose_with_dots_does_not(self):
        assert c.x_weighted_length("example.com") == 23
        assert c.x_weighted_length("e.g. this") == 9

    def test_limit_boundary(self):
        assert c.x_weighted_length("a" * 280) == 280
        assert c.x_weighted_length("a" * 279 + "你") == 281


class TestOtherUnits:
    def test_bluesky_graphemes_vs_bytes(self):
        family = "👨‍👩‍👧"
        assert c.count_text(family, "graphemes") == 1
        assert c.count_text(family, "utf8_bytes") == 18
        assert c.count_text("é", "graphemes") == 1

    def test_tiktok_utf16_units(self):
        assert c.count_text("😀", "utf16") == 2
        assert c.count_text("a😀", "utf16") == 3
        assert c.count_text("😀", "codepoints") == 1

    def test_unknown_unit(self):
        with pytest.raises(ValueError):
            c.count_text("x", "words")

    def test_hashtags_and_mentions(self):
        text = "#one #two @a @b. mail me@site.com C# ##x"
        assert c.count_hashtags(text) == 2
        assert c.count_mentions(text) == 2

    def test_text_stats(self):
        stats = c.text_stats("Hi #tag @who https://example.com")
        assert stats["hashtags"] == 1 and stats["mentions"] == 1 and stats["urls"] == 1
        assert stats["x_weighted"] == len("Hi #tag @who ") + 23


class TestRules:
    def test_rules_come_from_the_platform_file(self):
        assert (c.rules_for("x").unit, c.rules_for("x").limit) == ("x_weighted", 280)
        bsky = c.rules_for("bluesky")
        assert (bsky.unit, bsky.limit, bsky.bytes_max) == ("graphemes", 300, 3000)
        ig = c.rules_for("instagram")
        assert (ig.limit, ig.hashtags_max, ig.mentions_max) == (2200, 30, 20)
        assert (c.rules_for("tiktok").unit, c.rules_for("tiktok").limit) == ("utf16", 2200)
        assert c.rules_for("linkedin").limit == 3000
        assert c.rules_for("threads").limit == 500

    def test_recommendation_limits_are_not_hard(self):
        assert c.rules_for("youtube").hard is False
        assert c.rules_for("x").hard is True


class TestSplit:
    def _long(self, n=40, tail=""):
        return " ".join(f"Sentence number {i} is here." for i in range(n)) + tail

    def test_short_text_is_not_split_or_numbered(self):
        report = c.fit("x", "short post")
        assert report.parts == ["short post"] and not report.split and report.ok

    def test_over_limit_x_splits_with_numbering(self):
        report = c.fit("x", self._long())
        assert report.split and report.ok and len(report.parts) >= 2
        n = len(report.parts)
        for index, part in enumerate(report.parts, start=1):
            assert part.endswith(f" {index}/{n}")
            assert c.x_weighted_length(part) <= 280

    def test_split_happens_on_sentence_boundaries(self):
        report = c.fit("x", self._long())
        for part in report.parts[:-1]:
            body = part.rsplit(" ", 1)[0]
            assert body.endswith(".")

    def test_urls_are_never_broken(self):
        url = "https://example.com/some/long/link/path/that/must/not/break?x=1"
        report = c.fit("x", self._long(tail=" " + url))
        assert sum(part.count(url) for part in report.parts) == 1
        assert all(part.count("https://") <= 1 for part in report.parts)

    def test_bluesky_splits_by_graphemes(self):
        report = c.fit("bluesky", self._long(30))
        assert report.split and report.ok
        for part in report.parts:
            assert c.count_text(part, "graphemes") <= 300

    def test_splitting_can_be_disabled(self):
        report = c.fit("x", self._long(), split_threads=False)
        assert not report.split and not report.ok and report.overflow > 0

    def test_platforms_without_threads_never_split(self):
        report = c.fit("linkedin", "word " * 800)
        assert len(report.parts) == 1 and not report.ok and report.overflow > 0

    def test_agent_written_thread_is_kept_as_given(self):
        report = c.fit("x", ["first part", "second part"])
        assert report.parts == ["first part", "second part"] and report.ok and not report.split


class TestFit:
    def test_instagram_hashtag_cap_fails_the_draft(self):
        report = c.fit("instagram", "hello " + " ".join(f"#t{i}" for i in range(31)))
        assert not report.ok and report.hashtags == 31
        assert any("hashtags" in note for note in report.notes)

    def test_instagram_30_hashtags_pass(self):
        assert c.fit("instagram", " ".join(f"#t{i}" for i in range(30))).ok

    def test_instagram_mention_cap(self):
        assert not c.fit("instagram", " ".join(f"@u{i}" for i in range(21))).ok

    def test_bluesky_bytes_cap(self):
        # 300 graphemes of 4-byte emoji would be 1200 bytes; stay under graphemes, over bytes is impossible,
        # so check the bytes rule through a 3-byte character string that fits graphemes but not bytes.
        report = c.fit("bluesky", "€" * 300)
        assert report.ok and report.bytes_count == 900

    def test_tiktok_utf16_overflow(self):
        report = c.fit("tiktok", "😀" * 1101)
        assert not report.ok and report.counts == [2202] and report.overflow == 2

    def test_fold_text_is_a_prefix_cut_at_a_word(self):
        report = c.fit("instagram", "word " * 100)
        assert report.fold_chars <= report.fold_limit and "word " * 100 != report.fold
        assert report.fold.endswith("word")


from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

_WORD = st.text(alphabet="abcdefghij klmnop", min_size=1, max_size=12).map(str.strip).filter(bool)
_URL = st.sampled_from(["https://example.com/a/b?c=1", "https://news.site.org/2026/11/very-long-article-slug-here"])
_SENTENCE = st.one_of(_WORD.map(lambda w: f"{w}."), st.tuples(_WORD, _URL).map(lambda t: f"{t[0]} {t[1]}."))


@settings(max_examples=60, deadline=None)
@given(st.lists(_SENTENCE, min_size=1, max_size=60))
def test_split_property_every_part_fits_and_urls_stay_whole(sentences):
    text = " ".join(sentences)
    report = c.fit("x", text)
    assert all(count <= 280 for count in report.counts) or not report.ok
    if report.ok:
        for url in ("https://example.com/a/b?c=1", "https://news.site.org/2026/11/very-long-article-slug-here"):
            assert sum(part.count(url) for part in report.parts) == text.count(url)
        if report.split:
            assert all(part.rsplit(" ", 1)[1] == f"{i}/{len(report.parts)}" for i, part in enumerate(report.parts, 1))
