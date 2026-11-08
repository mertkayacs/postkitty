# Synthetic image fixtures

The image tests generate fixtures in each pytest temporary directory so the
repository does not carry opaque binaries.

- `single-face`: a solid background with one skin-tone ellipse and a matching
  `FakeDetector` box.
- `two-faces`: two separated skin-tone ellipses used for vertical split layouts.
- `five-person-group`: five ellipses spread across a wide frame for pad framing.
- `salient-object`: a dark frame with one bright rectangle and no face boxes.
- `transparent-shape`: an RGBA image used to verify PNG export and alpha retention.
