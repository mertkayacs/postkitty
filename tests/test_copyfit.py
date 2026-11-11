import json
from pathlib import Path

import pytest

from engine.text import fit as c

_CONFORMANCE = json.loads((Path(__file__).parent / "fixtures" / "twitter_text_weighted.json").read_text(encoding="utf-8"))


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

    @pytest.mark.parametrize("case", _CONFORMANCE["cases"], ids=lambda case: case["description"][:60])
    def test_twitter_text_conformance_suite(self, case):
        assert c.x_weighted_length(case["text"]) == case["weighted_length"]

    # Expected values below come from twitter-text 3.1.0 parseTweet() with the twemoji-parser 14.0.0 emoji table.
    @pytest.mark.parametrize("text, expected", [
        ("see https://example.com/" + "a" * 200 + " now", 4 + 23 + 4),
        ("https://en.wikipedia.org/wiki/Rust_(programming_language)", 23),  # balanced parentheses belong to the link
        ("(https://example.com)", 25),
        ("Read https://example.com.", 29),
        ("https://example.com/a,b.", 24),
        ("https://example.com/path日本語", 29),     # the link ends where the CJK text starts
        ("https://example.com🎉", 25),
        ("https://example.com\nhttps://example.org", 47),
        ("https://t.co/abc-def", 27),               # a t.co link ends with its slug
        ("https://пример.рф/путь", 23),
        ("example.com", 23),
        ("EXAMPLE.COM", 23),
        ("example.eu", 23),
        ("example.com/a?x=1", 23),
        ("example.com?x=1", 27),                    # without a path the query stays plain text
        ("example.com:8080", 28),
        ("README.md", 23),                          # .md and .py are country domains, so X links file names
        ("tools.py and SKILL.md", 51),
        ("plugin.yaml", 11),
        ("node.js", 7),
        ("v1.0.0", 6),
        ("e.g. this", 9),
        ("me@example.com", 14),                     # an email address is no link
        ("ftp://example.com", 17),
        ("http://localhost:3000/x", 23),
        ("Bitti.Şimdi", 11),
        ("BİLGİ.İNFO", 10),                         # Turkish dotted İ is not the ASCII I of .info
        ("bilgi.info", 23),
        ("#🎉.example.com", 27),
        ("example.com/abc–(c)", 27),                # a path does not end with a dash and a bracket pair
        ("x_y.com:8080.com", 16),                   # no underscore next to the top-level domain
        ("あ" * 20000 + ".", 40001),                 # long unspaced text is counted in linear time
        ("a." * 10000, 20000),
    ])
    def test_links_count_23_exactly_where_x_links_them(self, text, expected):
        assert c.x_weighted_length(text) == expected

    @pytest.mark.parametrize("text, expected", [
        ("❤️‍🔥", 2), ("🧔‍♂️", 2), ("🫱🏻‍🫲🏽", 2), ("🏴󠁧󠁢󠁥󠁮󠁧󠁿", 2), ("🏳️‍🌈", 2), ("⭐️", 2), ("©️", 2),
        ("🇹🇷🇩🇪", 4), ("👍🏽👍🏽", 4),
        ("©", 1),                                   # no emoji without its variation selector
        ("🧔‍♂", 5),                                 # the gender sign needs U+FE0F to form the sequence
        ("😀\u200d😀", 5),                          # a joiner between two emoji that form no known sequence
        ("⭐🏻", 4),                                 # a skin tone after an emoji that takes none
        ("🙂‍↔️", 5),                                # newer than the last Twemoji table
    ])
    def test_emoji_follow_the_twemoji_table(self, text, expected):
        assert c.x_weighted_length(text) == expected

    @pytest.mark.parametrize("text, expected", [
        ("…", 2), ("“”", 2), ("—", 1), ("€", 2), ("₺", 2), ("™", 2), ("→", 2), ("•", 2), ("ß", 1), ("ẞ", 2),
        ("ı", 1), ("İ", 1), ("ع", 1), ("ש", 1), ("я", 1), ("한", 2), ("\u200b", 1), ("\r\n", 2), ("\t", 1),
    ])
    def test_single_characters(self, text, expected):
        assert c.x_weighted_length(text) == expected

    def test_limit_boundary(self):
        assert c.x_weighted_length("a" * 280) == 280
        assert c.x_weighted_length("a" * 279 + "你") == 281

    def test_decomposed_accents_count_like_their_nfc_form(self):
        # twitter-text parseTweet() normalizes to NFC before weighting, so "e" + U+0301 is one character.
        assert c.x_weighted_length("café") == c.x_weighted_length("café") == 4
        assert c.x_weighted_length("Istanbul'da çay içtik") == len("Istanbul'da çay içtik")


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


class TestThreadsUnit:
    # Threads API, text parameter: "For the post character limit, emojis are counted as the number of UTF-8 bytes."
    @pytest.mark.parametrize("text", [
        "hello world", "Çağrı için teşekkürler, İstanbul ışığı", "Grüße aus Köln, die Straße ist groß",
        "e\u0301", "日本語", "1 # *",
    ])
    def test_text_without_emoji_counts_one_per_character(self, text):
        assert c.count_text(text, "threads") == len(text)

    @pytest.mark.parametrize("text, expected", [
        ("😀", 4),
        ("👨‍👩‍👧‍👦", 25),   # family: four emoji of 4 bytes and three joiners of 3
        ("🇹🇷", 8),        # flag: two regional indicators
        ("👍🏽", 8),        # thumbs up and a skin tone
        ("1️⃣", 7),       # keycap: the digit, U+FE0F and U+20E3
        ("❤️", 6),        # heart and U+FE0F, 3 bytes each
        ("ok 👍", 7),
    ])
    def test_an_emoji_counts_its_utf8_bytes(self, text, expected):
        assert c.count_text(text, "threads") == expected

    def test_threads_limit_uses_the_unit(self):
        assert c.rules_for("threads").unit == "threads"
        assert c.fit("threads", "a" * 496 + "😀", split_threads=False).ok
        over = c.fit("threads", "a" * 497 + "😀", split_threads=False)
        assert not over.ok and over.counts == [501] and over.overflow == 1


class TestRules:
    def test_rules_come_from_the_platform_file(self):
        assert (c.rules_for("x").unit, c.rules_for("x").limit) == ("x_weighted", 280)
        bsky = c.rules_for("bluesky")
        assert (bsky.unit, bsky.limit, bsky.bytes_max) == ("graphemes", 300, 3000)
        ig = c.rules_for("instagram")
        assert (ig.limit, ig.hashtags_max, ig.mentions_max) == (2200, 5, 20)
        assert (c.rules_for("tiktok").unit, c.rules_for("tiktok").limit) == ("utf16", 2200)
        assert c.rules_for("linkedin").limit == 3000
        assert c.rules_for("threads").limit == 500

    def test_recommendation_limits_are_not_hard(self):
        assert c.rules_for("facebook").hard is False
        assert c.rules_for("x").hard is True

    def test_youtube_title_limit_is_hard(self):
        assert c.rules_for("youtube").hard is True
        assert c.fit("youtube", "a" * 100).ok
        over = c.fit("youtube", "a" * 101)
        assert not over.ok and over.overflow == 1


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

    def test_paragraph_breaks_survive_the_split(self):
        first = " ".join(["First paragraph sentence."] * 3)
        second = " ".join(["Second paragraph sentence."] * 3)
        third = " ".join(["Third paragraph sentence."] * 12)
        report = c.fit("x", f"{first}\n\n{second}\n{third}")
        assert report.split and report.ok
        assert report.parts[0].startswith(f"{first}\n\n{second}\n")
        assert all(part == part.strip() for part in report.parts)
        assert all(c.x_weighted_length(part) <= 280 for part in report.parts)

    def test_agent_written_thread_is_kept_as_given(self):
        report = c.fit("x", ["first part", "second part"])
        assert report.parts == ["first part", "second part"] and report.ok and not report.split


class TestFit:
    def test_instagram_hashtag_cap_fails_the_draft(self):
        report = c.fit("instagram", "hello " + " ".join(f"#t{i}" for i in range(31)))
        assert not report.ok and report.hashtags == 31
        assert any("hashtags" in note for note in report.notes)

    def test_instagram_allows_five_hashtags_and_not_six(self):
        assert c.fit("instagram", " ".join(f"#t{i}" for i in range(5))).ok
        assert not c.fit("instagram", " ".join(f"#t{i}" for i in range(6))).ok

    def test_instagram_mention_cap(self):
        assert not c.fit("instagram", " ".join(f"@u{i}" for i in range(21))).ok

    def test_bluesky_bytes_cap(self):
        # 300 graphemes of 4-byte emoji would be 1200 bytes; stay under graphemes, over bytes is impossible,
        # so check the bytes rule through a 3-byte character string that fits graphemes but not bytes.
        report = c.fit("bluesky", "€" * 300)
        assert report.ok and report.bytes_count == 900

    def test_bluesky_bytes_cap_applies_to_each_post_of_a_thread(self):
        report = c.fit("bluesky", " ".join("ğüşiöç" * 6 + "." for _ in range(120)))
        assert report.split and report.ok and report.bytes_count > 3000
        assert not any("bytes" in note for note in report.notes)
        over = c.fit("bluesky", ["👨‍👩‍👧‍👦" * 121, "ok"])
        assert not over.ok and any("3000 UTF-8 bytes" in note and "3025" in note for note in over.notes)

    def test_tiktok_utf16_overflow(self):
        report = c.fit("tiktok", "😀" * 1101)
        assert not report.ok and report.counts == [2202] and report.overflow == 2

    def test_fold_text_is_a_prefix_cut_at_a_word(self):
        report = c.fit("instagram", "word " * 100)
        assert report.fold_chars <= report.fold_limit and "word " * 100 != report.fold
        assert report.fold.endswith("word")

    def test_fold_never_cuts_inside_an_emoji_or_an_accented_letter(self):
        family = "👨‍👩‍👧‍👦"  # seven code points, one visible character
        fold = c.fit("instagram", family * 40).fold
        assert fold == family * 17 and len(fold) <= 125
        assert c.fit("instagram", "e\u0301" * 100).fold == "e\u0301" * 62

    def test_fold_of_a_platform_without_a_fold_is_its_whole_limit(self):
        report = c.fit("youtube", "a" * 150)
        assert (report.fold_limit, report.fold_chars) == (100, 100)


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
