"""Review board: board.html, board-inline.html and contact.png for a postkitty job.

Only the standard library and Pillow are used. Every value that comes from the
manifest is passed through html.escape before it reaches the page.
"""

from __future__ import annotations

import base64
import html
import io
import json
import mimetypes
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

POSSY_SVG = (
    '<svg viewBox="168 8 688 688" xmlns="http://www.w3.org/2000/svg" '
    'width="688" height="688" aria-label="Possy, the postkitty mascot">'
    '<title>Possy, the postkitty mascot</title>'
    '<g transform="translate(61 54) scale(.88)" stroke="#1E2A44" stroke-width="14" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<g id="body">'
    '<path d="M300 715C244 747 216 798 226 859C182 865 149 903 157 947C168 1002 '
    '239 1027 318 1026C366 1025 403 1005 402 974L441 988C478 1002 534 1001 565 988 '
    'C608 1001 664 996 689 979C713 961 700 933 688 917C732 858 711 796 670 757L659 '
    '657Z" fill="#E8814D" />'
    '<path d="M667 767C674 825 663 884 654 924" fill="none" />'
    '<path d="M252 761C295 759 340 786 352 819C361 847 341 833 322 822C295 804 264 '
    '799 235 803Z" fill="#C8643A" stroke="none" />'
    '<path d="M229 837C266 830 312 847 327 869C342 891 314 881 293 877C272 873 251 '
    '874 231 881Z" fill="#C8643A" stroke="none" />'
    '<path d="M178 899C202 875 225 880 244 893C204 916 192 945 198 974L172 952Z" '
    'fill="#C8643A" stroke="none" />'
    '<path d="M275 914C244 945 230 981 246 1017L285 1025C265 985 280 952 312 927Z" '
    'fill="#C8643A" stroke="none" />'
    '<path d="M344 937C314 961 305 995 321 1025C370 1026 402 1005 402 974C400 957 '
    '375 942 344 937Z" fill="#C8643A" stroke="none" />'
    '<path d="M387 758C430 803 433 855 420 908L433 938" fill="none" stroke-width="11" />'
    '<path d="M515 690C526 760 538 841 547 924" fill="none" />'
    '<path d="M425 925C457 898 512 902 544 927C565 945 577 975 562 990C536 1005 '
    '469 1006 438 994C451 966 441 942 425 925Z" fill="#F7F1E5" />'
    '<path d="M558 928C585 902 632 901 662 916C691 931 705 960 692 978C666 996 '
    '598 997 562 985C570 965 565 946 558 928Z" fill="#F7F1E5" />'
    '<path d="M486 952Q503 977 493 997M530 952Q545 975 538 996M610 950Q622 970 613 '
    '990M652 949Q665 967 658 987" fill="none" stroke-width="7" />'
    '<path d="M352 933C379 914 410 918 429 940C448 960 451 982 438 994C420 1005 '
    '389 1005 372 1000" fill="#F7F1E5" />'
    '<path d="M404 959Q417 982 407 1000" fill="none" stroke-width="7" />'
    '<path d="M226 859C229 900 258 915 304 920C350 926 393 939 400 968C410 1006 '
    '371 1027 318 1026C242 1027 169 1003 157 947C149 903 182 866 226 859" fill="none" />'
    '</g>'
    '<g id="arms">'
    '<path d="M300 531C259 563 251 640 278 683C305 728 368 732 411 699C435 680 457 '
    '646 463 607Z" fill="#E8814D" />'
    '<path d="M267 617C294 642 326 645 356 632C379 623 362 658 342 670C316 687 286 '
    '677 277 666Z" fill="#C8643A" stroke="none" />'
    '<path d="M602 601C614 646 625 704 666 721C720 741 775 694 796 636L815 551L736 '
    '526Z" fill="#E8814D" />'
    '<path d="M721 618C746 638 770 644 794 631C786 657 773 676 755 686C732 685 714 '
    '666 705 643C697 622 702 606 721 618Z" fill="#C8643A" stroke="none" />'
    '</g>'
    '<path id="bib" d="M481 605C454 622 437 661 448 684C453 695 469 679 480 667 '
    'C469 699 475 739 490 752C501 764 508 734 513 725C519 771 529 815 538 843C564 '
    '816 582 780 589 746L596 769C621 750 635 704 623 674C643 713 651 681 641 650 '
    'C633 623 610 608 594 597Z" fill="#F7F1E5" stroke="none" />'
    '<g id="head">'
    '<path d="M205 342C170 280 166 190 179 126C189 77 203 47 236 48C293 47 354 84 '
    '397 119C443 98 494 88 547 92C586 38 645 -31 681 -23C721 -13 777 92 794 225 '
    'C823 266 853 321 852 371C851 443 800 493 731 536C652 586 542 615 432 607C349 '
    '602 260 589 220 546C165 489 164 410 205 342Z" fill="#E8814D" />'
    '<path d="M199 325C174 261 178 163 194 112C203 83 218 65 243 76C280 93 313 130 '
    '336 168C279 210 235 264 199 325Z" fill="#F2B8A2" stroke="none" />'
    '<path d="M558 92C602 35 649 -10 676 -7C646 23 632 66 624 109Z" fill="#E8814D" '
    'stroke="none" />'
    '<path d="M624 109C637 56 654 4 676 -7C715 7 765 109 780 206C736 157 684 126 '
    '624 109Z" fill="#F2B8A2" stroke="none" />'
    '<path d="M243 76C285 96 315 129 343 169C281 215 239 271 209 326M624 109C636 57 '
    '654 12 672 4" fill="none" stroke-width="9" />'
    '<path d="M390 133C419 156 443 183 466 214C487 239 495 223 487 198C478 163 458 '
    '132 438 111Z" fill="#C8643A" stroke="none" />'
    '<path d="M472 99C504 129 520 167 540 210C553 238 571 229 568 196C565 153 548 '
    '117 527 93Z" fill="#C8643A" stroke="none" />'
    '<path d="M562 94C583 122 592 149 601 175C611 202 627 188 628 159C630 135 624 '
    '119 617 108Z" fill="#C8643A" stroke="none" />'
    '<path d="M190 377C237 348 287 346 322 363C343 373 336 384 318 386C265 391 221 '
    '411 181 439Z" fill="#C8643A" stroke="none" />'
    '<path d="M191 480C224 452 266 438 293 443C315 447 300 459 283 469C247 491 219 '
    '519 214 537Z" fill="#C8643A" stroke="none" />'
    '<path d="M822 307C795 310 776 323 773 339C771 351 805 340 839 356Z" '
    'fill="#C8643A" stroke="none" />'
    '<path d="M844 384C818 370 787 372 784 384C780 394 816 408 825 436C838 418 845 '
    '403 844 384Z" fill="#C8643A" stroke="none" />'
    '<path d="M327 482C358 457 401 459 437 448C488 433 514 372 559 371C602 369 619 '
    '401 654 401C699 385 741 401 756 436C780 484 725 530 675 553C596 591 512 610 '
    '432 601C380 597 330 585 310 561Z" fill="#F7F1E5" stroke="none" />'
    '<path d="M383 410C382 360 422 319 465 333C506 344 527 393 509 430C488 470 426 '
    '466 400 438Z" fill="#F7F1E5" stroke="none" />'
    '<path d="M385 410C384 369 420 326 461 330" fill="none" />'
    '<ellipse cx="475" cy="392" rx="52" ry="59" fill="#1E2A44" stroke="none" />'
    '<circle cx="487" cy="365" r="17" fill="#F7F1E5" stroke="none" />'
    '<ellipse cx="691" cy="338" rx="53" ry="62" transform="rotate(-16 691 338)" '
    'fill="#F7F1E5" stroke="none" />'
    '<ellipse cx="675" cy="345" rx="44" ry="58" transform="rotate(-16 675 345)" '
    'fill="#1E2A44" stroke="none" />'
    '<circle cx="663" cy="319" r="16" fill="#F7F1E5" stroke="none" />'
    '<path d="M410 303Q437 273 469 290M628 219Q650 195 678 215" fill="none" '
    'stroke-width="11" />'
    '<ellipse cx="414" cy="487" rx="41" ry="17" transform="rotate(-8 414 487)" '
    'fill="#F2B8A2" stroke="none" />'
    '<ellipse cx="724" cy="422" rx="34" ry="16" transform="rotate(-7 724 422)" '
    'fill="#F2B8A2" stroke="none" />'
    '<path d="M579 401C591 390 619 388 628 396C631 407 618 423 608 424C594 423 '
    '570 414 579 401Z" fill="#E07A5F" stroke="none" />'
    '<path d="M568 453C582 490 602 509 621 494C637 481 641 452 642 437C624 446 612 '
    '438 607 432C596 449 584 455 568 453Z" fill="#E07A5F" stroke-width="7" />'
    '<path d="M608 423L607 432C593 454 574 460 558 449M607 432C624 443 643 441 650 '
    '430" fill="none" stroke-width="7" />'
    '</g>'
    '<g id="viewfinder" fill="none" stroke-width="27">'
    '<path d="M336 324V263H402" />'
    '<path d="M667 263H732V322" stroke="#F7F1E5" stroke-width="35" />'
    '<path d="M667 263H732V322" />'
    '<path d="M337 486V548H404" />'
    '<path d="M732 479V543H667" />'
    '</g>'
    '<g id="paws" fill="#F7F1E5">'
    '<path d="M363 548C365 519 340 503 313 513C277 523 255 554 263 589C268 618 '
    '292 638 321 638C349 638 365 619 360 597C382 578 383 560 363 548Z" />'
    '<path d="M794 518C770 508 744 517 723 538C707 554 706 574 721 584C705 602 '
    '716 626 742 631C778 639 808 617 820 588C832 556 820 531 794 518Z" />'
    '<path d="M305 559C325 544 346 543 363 548M360 597L340 603M721 554C739 543 757 '
    '549 772 559M721 584C732 579 745 582 754 589" fill="none" stroke-width="8" />'
    '</g>'
    '</g>'
    '</svg>'
)

CREAM = "#F7F1E5"
NAVY = "#1E2A44"
GINGER = "#E8814D"
TERRACOTTA = "#E07A5F"
MUTED = "#5B6478"

INK = "#243046"
BORDER = "#D9CFA9"
SURFACE = "#FFFFFF"

STATUS_COLORS = {
    "ready": "#14532d",
    "repaired": "#92400e",
    "advisory": "#715711",
    "failed": "#7f1d1d",
    "skipped": "#5B6478",
}
STATUS_LABELS = {
    "ready": "Ready",
    "repaired": "Repaired",
    "advisory": "Advisory",
    "failed": "Failed",
    "skipped": "Skipped",
}

CSS = """\
:root {
  --pk-foreground: var(--foreground, #1E2A44);
  --pk-muted-foreground: var(--muted-foreground, #5B6478);
  --pk-accent: var(--accent, #E8814D);
  --pk-border: var(--border, #D9CFA9);
  --pk-card: var(--card, #FFFFFF);
  --pk-ink: var(--pk-foreground);
  --pk-muted: var(--pk-muted-foreground);
  --pk-bg: #F7F1E5;
  --pk-surface: var(--pk-card);
}
@media (prefers-color-scheme: dark) {
  :root {
    --pk-bg: #141B2B;
    --pk-ink: var(--foreground, #F5EFE2);
    --pk-muted: var(--muted-foreground, #C9CBD6);
    --pk-border: var(--border, #3B465B);
    --pk-surface: var(--card, #1E2A44);
  }
}
* { box-sizing: border-box; }
html { scroll-padding-top: 72px; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  background: var(--pk-bg);
  color: var(--pk-ink);
  line-height: 1.5;
  font-size: 16px;
}
h1, h2, h3, h4, .serif {
  font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
}
.visually-hidden {
  position: absolute;
  width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}
.toast {
  position: fixed;
  inset-inline-end: 16px;
  inset-block-end: 16px;
  background: var(--pk-ink);
  color: #F7F1E5;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease, transform 0.2s ease;
  transform: translatey(10px);
  z-index: 100;
}
@media (prefers-reduced-motion: no-preference) {
  .toast.show { opacity: 1; transform: translatey(0); }
}
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
  .toast.show { opacity: 1; transform: none; }
}
.header {
  padding: 28px 24px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.possy-mark { width: 40px; height: 40px; display: block; flex-shrink: 0; }
.possy-mark svg { width: 40px; height: 40px; display: block; }
.header .title-group { min-width: 0; }
.header h1 {
  font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: normal;
  letter-spacing: 0.008em;
  color: var(--pk-ink);
}
.header .created {
  color: var(--pk-muted);
  font-size: 14px;
}
.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-left: auto;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--pk-border);
  border-radius: 999px;
  background: var(--pk-surface);
  color: var(--pk-ink);
  font-size: 13px;
  font-weight: 600;
}
.chip .value { font-variant-numeric: tabular-nums; }
.section {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}
.advice {
  border: 1px solid var(--pk-border);
  border-radius: 14px;
  background: var(--pk-surface);
  padding: 22px 26px;
  margin-bottom: 8px;
}
.advice h2 {
  font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  margin: 0 0 12px 0;
  font-size: 20px;
  font-weight: normal;
  color: var(--pk-ink);
}
.advice p { margin: 0 0 10px 0; color: var(--pk-ink); }
.advice .field { margin-bottom: 14px; }
.advice .field .label {
  display: block;
  color: var(--pk-muted);
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}
.advice ul { margin: 0 0 0 16px; padding: 0; color: var(--pk-ink); }
.advice li { margin-bottom: 6px; }
.platform-group { margin-bottom: 40px; }
.platform-group h2 {
  font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  margin: 0 0 14px 0;
  font-size: 20px;
  font-weight: normal;
  color: var(--pk-ink);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--pk-border);
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 20px;
}
@media (min-width: 740px) {
  .card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (min-width: 1180px) {
  .card-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
.target-card {
  border: 1px solid var(--pk-border);
  border-radius: 14px;
  background: var(--pk-surface);
  display: flex;
  flex-direction: column;
  height: 100%;
}
.target-card .status-strip {
  padding: 10px 14px;
  border-bottom: 1px solid var(--pk-border);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 700;
}
.target-card .hard-banner {
  background: #FBEDEC;
  border: 1px solid #E07A5F;
  color: #7f1d1d;
  padding: 10px 14px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.target-card .hard-banner .b-icon { flex-shrink: 0; }
.frame-wrap {
  position: relative;
  margin: 14px;
  isolation: isolate;
}
.frame {
  border: 1px solid var(--pk-border);
  border-radius: 10px;
  background: #0B1120;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.frame.phone { aspect-ratio: 9 / 16; width: 100%; }
.frame.feed { aspect-ratio: 1 / 1; width: 100%; max-height: 260px; }
.frame .earpiece {
  position: absolute;
  inset-block-start: 10px;
  inset-inline-start: 50%;
  transform: translatex(-50%);
  width: 20%; height: 7px;
  background: #C9CBD6;
  border-radius: 4px;
}
.frame .screen {
  width: 100%; height: 100%;
  position: relative;
  overflow: hidden;
  background: #0B1120;
}
.frame video, .frame img {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
  background: #0B1120;
}
.frame.feed video, .frame.feed img { object-fit: contain; background: #FFFFFF; }
.toggle-safe-area {
  position: absolute;
  inset-block-start: 10px;
  inset-inline-end: 10px;
  z-index: 5;
  background: rgba(20, 27, 43, 0.75);
  color: #FFFFFF;
  border: 1px solid rgba(255, 255, 255, 0.5);
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  cursor: pointer;
}
@media (prefers-reduced-motion: no-preference) {
  .safe-area { transition: opacity 0.2s ease; }
}
.safe-area {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0;
}
.safe-area.show { opacity: 1; }
.safe-area band {
  position: absolute;
  background: rgba(232, 129, 77, 0.35);
  border: 1px dashed rgba(232, 129, 77, 0.7);
}
.safe-area band.top { inset-block-start: 0; inset-inline: 0; height: var(--top); }
.safe-area band.bottom { inset-block-end: 0; inset-inline: 0; height: var(--bottom); }
.safe-area band.left { inset-block: var(--top) calc(100% - var(--bottom)); inset-inline-start: 0; width: var(--side); }
.safe-area band.right { inset-block: var(--top) calc(100% - var(--bottom)); inset-inline-end: 0; width: var(--side); }
.media-box {
  margin: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.media-box .alt-text {
  color: var(--pk-muted);
  font-size: 13px;
}
.copy-box {
  margin: 14px 14px 8px 14px;
}
.part-badge {
  color: var(--pk-muted);
  font-size: 12px;
  margin-bottom: 2px;
}
.copy-box p {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.fold {
  color: var(--pk-accent);
  font-weight: 700;
  font-size: 12px;
}
.count-line {
  margin: 4px 14px 12px 14px;
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}
.count-line .count { color: var(--pk-ink); font-weight: 700; }
.count-line .unit { color: var(--pk-muted); font-weight: 600; }
.count-line .ok { color: #14532d; }
.count-line .over { color: #7f1d1d; }
.layout-note {
  margin: 0 14px 8px 14px;
  font-size: 13px;
  color: var(--pk-muted);
}
.repairs {
  margin: 0 14px 8px 14px;
  font-size: 13px;
  color: #715711;
}
.checks details {
  margin: 0 14px 14px 14px;
  border: 1px solid var(--pk-border);
  border-radius: 10px;
  background: var(--pk-surface);
  overflow: hidden;
}
.checks summary {
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 700;
  list-style: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}
@media (prefers-reduced-motion: no-preference) {
  .checks .check-row { transition: background 0.15s ease; }
}
.checks .check-row {
  border-bottom: 1px solid var(--pk-border);
  padding: 8px 14px;
  font-size: 12.5px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.checks .check-row:last-child { border-bottom: none; }
.checks .badge {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: 6px;
  color: #FFFFFF;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.checks .id { color: var(--pk-muted); min-width: 150px; }
.checks .measured { color: var(--pk-ink); font-variant-numeric: tabular-nums; }
.checks .expected { color: var(--pk-muted); }
.checks .message { margin-left: auto; max-width: 42%; }
.checks .source {
  margin-left: auto;
  font-size: 11px;
  color: var(--pk-muted);
}
.checks .source a { color: var(--pk-ink); text-decoration: underline; text-underline-offset: 2px; }
.actions {
  margin: 10px 14px 16px 14px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.button, button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--pk-border);
  border-radius: 10px;
  background: var(--pk-surface);
  color: var(--pk-ink);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  line-height: normal;
}
@media (prefers-reduced-motion: no-preference) {
  button:not([disabled]):hover { transform: translatey(-1px); }
  button:active { transform: scale(0.97); }
}
button:focus-visible {
  outline: 3px solid #E8814D;
  outline-offset: 2px;
}
.button.primary, button.primary {
  background: #1E2A44;
  color: #FFFFFF;
  border-color: #1E2A44;
}
.button.ghost { color: #5B6478; }
.button.danger { background: #7f1d1d; border-color: #7f1d1d; color: #FFFFFF; }
.hermes-status {
  font-size: 12px;
  color: var(--pk-muted);
  margin-left: 8px;
}
.empty {
  grid-column: 1 / -1;
  padding: 40px;
  color: var(--pk-muted);
  text-align: center;
}
@media (prefers-color-scheme: dark) {
  .frame.feed video, .frame.feed img { background: #0B1120; }
  .target-card .hard-banner { background: #3E1E18; border-color: #7f1d1d; color: #F5CFC6; }
}
"""

HTML_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
"""


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def esc_attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


def status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "#5B6478")
    return (
        f'<span class="badge" style="background:{esc_attr(color)};">'
        f'{esc(STATUS_LABELS.get(status, status))}</span>'
    )


def target_frame_class(target: dict) -> str:
    width = int(target.get("width") or 0)
    height = int(target.get("height") or 0)
    if width > 0 and height > 0 and (width / height) < 0.9:
        return "phone"
    return "feed"


def safe_area_bands(checks: list[dict]) -> str:
    for check in checks:
        measured = check.get("measured")
        if isinstance(measured, dict) and {"top", "bottom", "side"} <= set(measured):
            top = float(measured["top"])
            bottom = float(measured["bottom"])
            side = float(measured["side"])
            return (
                '<div class="safe-area" style="'
                f"--top: {top * 100:.2f}%; --bottom: {bottom * 100:.2f}%; --side: {side * 100:.2f}%;"
                '">'
                '<band class="top"></band>'
                '<band class="bottom"></band>'
                '<band class="left"></band>'
                '<band class="right"></band>'
                "</div>"
            )
    return ""


def media_html(target: dict, inline: bool, cache: dict, base_dir: Path,
               max_side: int = 720, quality: int = 80) -> str:
    kind = target.get("kind")
    file_rel = target.get("file") or ""
    cover_rel = target.get("cover")
    alt = target.get("alt") or ""
    if kind == "video":
        mime = mimetypes.guess_type(file_rel)[0] or "video/mp4"
        file_name = os.path.basename(file_rel)
        if inline:
            poster = image_data_uri_capped(base_dir / cover_rel, cache, max_side,
                                           quality) if cover_rel else ""
            play = (
                '<svg class="play-badge" viewBox="0 0 32 32" aria-hidden="true">'
                '<circle cx="16" cy="16" r="14" fill="#1E2A44" opacity="0.85"/>'
                '<path d="M11 12.3l8 5.7v-11.4z" fill="#F7F1E5"/>'
                '</svg>'
            )
            return (
                '<div class="video-media">'
                + (f'<img src="{esc_attr(poster)}" alt="Poster for {esc_attr(file_name)}" class="poster">' if poster else "")
                + play
                + f'<span class="file-name">{esc(file_name)}</span>'
                + '</div>'
            )
        poster_attr = f' poster="{esc_attr(cover_rel)}"' if cover_rel else ""
        return (
            '<div class="video-media">'
            f'<video controls muted playsinline loop preload="metadata"{poster_attr}>'
            f'<source src="{esc_attr(file_rel)}" type="{esc_attr(mime)}"></video>'
            f'<span class="file-name">{esc(file_name)}</span>'
            '</div>'
        )
    if kind == "image":
        src = image_data_uri_capped(base_dir / file_rel, cache, max_side, quality) if inline \
            else file_rel
        return f'<img src="{esc_attr(src)}" alt="{esc_attr(alt)}" class="thumb">'
    return f'<div class="missing-media">{esc(kind or "media")}</div>'


def image_data_uri_capped(path: Any, cache: dict, max_side: int, quality: int) -> str:
    if not path:
        return ""
    key = ("inline", str(path), max_side, quality)
    if key in cache:
        return cache[key]
    full = Path(path)
    if not full.is_file():
        return ""
    mime, _ = mimetypes.guess_type(str(full))
    mime = mime or "application/octet-stream"
    if not mime.startswith("image/"):
        return ""
    try:
        with Image.open(full) as image:
            image = ImageOps_exif_transpose(image)
            image = image.convert("RGB")
            image.thumbnail((max_side, max_side), Image.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = base64.b64encode(buffer.getvalue()).decode("ascii")
        result = f"data:image/jpeg;base64,{data}"
    except Exception:
        return ""
    cache[key] = result
    return result


def ImageOps_exif_transpose(image: Image.Image) -> Image.Image:
    try:
        from PIL import ImageOps
        return ImageOps.exif_transpose(image)
    except Exception:
        return image


def copy_info(manifest: dict, platform: str) -> dict:
    return (manifest.get("copy") or {}).get(platform, {}) or {}


def format_duration(seconds: Any) -> str:
    try:
        total = float(seconds)
    except (TypeError, ValueError):
        return ""
    total = max(0.0, total)
    minutes = int(total // 60)
    secs = int(round(total % 60))
    if minutes:
        return f"{minutes}:{secs:02d}"
    return f"{secs} s"


def build_target_card(target: dict, manifest: dict, alt_texts: dict, inline: bool,
                      cache: dict, job_id: str, base_dir: Path, max_side: int = 720,
                      quality: int = 80) -> str:
    status = target.get("status", "unknown")
    checks = target.get("checks") or []
    repairs = target.get("repairs") or []
    hard_fails = [c for c in checks if c.get("hard") and c.get("status") == "fail"]

    hard_html = ""
    if hard_fails:
        messages = " ".join(esc(c.get("message", "")) for c in hard_fails)
        hard_html = (
            '<div class="hard-banner">'
            '<span class="b-icon" aria-hidden="true">!</span>'
            f'<span>{esc(STATUS_LABELS["failed"].upper())}: {messages}</span>'
            '</div>'
        )

    frame_class = target_frame_class(target)
    bands = safe_area_bands(checks)
    toggle = (
        '<button type="button" class="toggle-safe-area" data-toggle-safe-area>'
        'Show safe area</button>' if bands else ""
    )
    ear = '<div class="earpiece"></div>' if frame_class == "phone" else ""
    file_rel = target.get("file") or ""
    alt = alt_texts.get(target.get("id")) or alt_texts.get(os.path.basename(file_rel)) or ""
    target = {**target, "alt": alt}
    media = media_html(target, inline, cache, base_dir, max_side, quality)

    platform = target.get("platform", "")
    copy = copy_info(manifest, platform)
    parts = copy.get("parts") or []
    counts = copy.get("counts") or []
    unit = copy.get("unit") or ""
    limit = copy.get("limit")
    copy_ok = copy.get("ok")

    copy_html = ""
    if parts:
        rendered_parts = []
        for index, part in enumerate(parts):
            suffix = f' <span class="part-badge">Part {index + 1} of {len(parts)}</span>' if len(parts) > 1 else ""
            rendered_parts.append(f'<p>{esc(part)}</p>{suffix}')
            if index < len(parts) - 1:
                rendered_parts.append('<span class="fold">... more</span>')
        copy_html = '<div class="copy-box">' + "".join(rendered_parts) + "</div>"
        count_text = ""
        if limit is not None:
            measured = max(counts) if counts else 0
            count_text = (
                f'<span class="count">{esc(measured)}</span> / '
                f'<span class="limit">{esc(limit)}</span> '
                f'<span class="unit">{esc(unit)}</span>'
                f' <span class="{"ok" if copy_ok else "over"}">'
                f'{"within limit" if copy_ok else "over limit"}</span>'
            )
        copy_html += f'<div class="count-line">{count_text}</div>'

    layout = target.get("layout") or {}
    note = layout.get("note") or ""
    layout_html = f'<div class="layout-note">{esc(note)}</div>' if note else ""

    repairs_html = ""
    if repairs:
        items = []
        for repair in repairs:
            action = esc(repair.get("action", ""))
            check = esc(repair.get("check", ""))
            ok = repair.get("ok")
            items.append(
                f'{action}{(" fixed " + esc(check)) if check else ""}'
                + ("." if ok else " (not resolved).")
            )
        repairs_html = (
            '<div class="repairs">Repairs: ' + " ".join(items) + "</div>"
        )

    checks_items = []
    for check in checks:
        measured = check.get("measured")
        expected = check.get("expected")
        measured_s = json.dumps(measured) if not isinstance(measured, str) else measured
        expected_s = json.dumps(expected) if not isinstance(expected, str) else expected
        source = ""
        source_url = check.get("source_url")
        checked_on = check.get("checked_on")
        if source_url:
            date_part = f" (checked {esc(checked_on)})" if checked_on else ""
            source = (
                '<span class="source">'
                f'<a href="{esc_attr(source_url)}">source</a>{esc(date_part)}'
                "</span>"
            )
        checks_items.append(
            '<div class="check-row">'
            f'{status_badge(check.get("status", ""))}'
            f'<span class="id">{esc(check.get("id", ""))}</span>'
            f'<span class="measured">{esc(measured_s)}</span>'
            f'<span class="expected">of {esc(expected_s)}</span>'
            f'<span class="message">{esc(check.get("message", ""))}</span>'
            f'{source}'
            "</div>"
        )
    checks_html = ""
    if checks:
        summary_badge = status_badge(status)
        checks_html = (
            '<div class="checks">'
            f'<summary>{esc(STATUS_LABELS.get(status, status))} '
            f'<span class="check-count">({len(checks)})</span>{summary_badge}</summary>'
            + "".join(checks_items)
            + "</div>"
        )

    redo_prompts = {
        "Focus left person": f"Use postkitty_redo on job {esc(job_id)} target {esc(target.get('id',''))} with focus left",
        "Focus right person": f"Use postkitty_redo on job {esc(job_id)} target {esc(target.get('id',''))} with focus right",
        "Split": f"Use postkitty_redo on job {esc(job_id)} target {esc(target.get('id',''))} with layout split",
        "Fit whole frame": f"Use postkitty_redo on job {esc(job_id)} target {esc(target.get('id',''))} with layout pad",
    }
    trim = target.get("trim")
    if trim and len(trim) == 2:
        redo_prompts["Trim"] = (
            f"Use postkitty_redo on job {esc(job_id)} target {esc(target.get('id',''))} "
            f"with trim {float(trim[0])}, {float(trim[1])}"
        )

    action_buttons = []
    caption = ""
    if parts:
        caption = "\n\n".join(str(p) for p in parts)
    if file_rel:
        action_buttons.append(
            f'<a class="button" href="{esc_attr(file_rel)}">Open file</a>'
        )
    if caption:
        action_buttons.append(
            f'<button type="button" class="button ghost" data-copy-caption="{esc_attr(caption)}">'
            'Copy caption</button>'
        )
    for label, prompt in redo_prompts.items():
        action_buttons.append(
            f'<button type="button" class="button" data-hermes-send="{esc_attr(prompt)}">{esc(label)}</button>'
        )
    action_buttons.append(
        '<span class="hermes-status"></span>'
    )

    return (
        '<article class="target-card">'
        f'<div class="status-strip">{esc(target.get("id",""))} {status_badge(status)}</div>'
        f'{hard_html}'
        f'<div class="frame-wrap">{toggle}'
        f'<div class="frame {frame_class}">{ear}'
        f'<div class="screen">{bands}{media}</div>'
        '</div></div>'
        f'{copy_html}{layout_html}{repairs_html}{checks_html}'
        f'<div class="actions">{"".join(action_buttons)}</div>'
        '</article>'
    )


def build_header(job_name: str, created: str, chips: list[tuple[str, int]]) -> str:
    items = []
    for label, count in chips:
        items.append(
            f'<span class="chip">{esc(label)} <span class="value">{count}</span></span>'
        )
    return (
        '<header class="header">'
        f'<div class="possy-mark">{POSSY_SVG}</div>'
        '<div class="title-group">'
        f'<h1>{esc(job_name)}</h1>'
        f'<div class="created">{esc(created)}</div>'
        '</div>'
        f'<div class="chips">{"".join(items)}</div>'
        '</header>'
    )


def build_advice(manifest: dict) -> str:
    advice = manifest.get("advice") or {}
    if not advice:
        return ""
    parts = ['<section class="advice">']
    topic = advice.get("topic")
    audience = advice.get("audience")
    tone = advice.get("tone")
    key_message = advice.get("key_message")
    if topic:
        parts.append('<div class="field"><span class="label">Topic</span>'
                     f'<p>{esc(topic)}</p></div>')
    if audience:
        parts.append('<div class="field"><span class="label">Audience</span>'
                     f'<p>{esc(audience)}</p></div>')
    if tone:
        parts.append('<div class="field"><span class="label">Tone</span>'
                     f'<p>{esc(tone)}</p></div>')
    if key_message:
        parts.append('<div class="field"><span class="label">Key message</span>'
                     f'<p>{esc(key_message)}</p></div>')
    ranking = advice.get("ranking") or []
    if isinstance(ranking, list) and ranking:
        parts.append('<div class="field"><span class="label">Platform ranking</span>'
                     '<ol>')
        for item in ranking:
            if not isinstance(item, dict):
                continue
            platform = str(item.get("platform") or "")
            reason = str(item.get("reason") or "")
            parts.append(
                f'<li><strong>{esc(platform)}</strong> {esc(reason) if reason else ""}</li>'
            )
        parts.append('</ol></div>')
    tips = advice.get("tips") or []
    if isinstance(tips, list) and tips:
        parts.append('<div class="field"><span class="label">Tips</span><ul>')
        for tip in tips:
            if str(tip).strip():
                parts.append(f'<li>{esc(str(tip))}</li>')
        parts.append('</ul></div>')
    parts.append("</section>")
    return "".join(parts)


def group_targets(manifest: dict) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for target in manifest.get("targets") or []:
        platform = target.get("platform") or "other"
        if platform not in grouped:
            grouped[platform] = []
            order.append(platform)
        grouped[platform].append(target)
    return [(platform, grouped[platform]) for platform in order]


def target_status_tally(targets: list[dict]) -> dict[str, int]:
    tally = {key: 0 for key in ("ready", "repaired", "failed", "skipped")}
    advisory = 0
    for target in targets:
        status = target.get("status")
        if status in tally:
            tally[status] += 1
        for check in target.get("checks") or []:
            if check.get("status") == "advisory":
                advisory += 1
    failed = tally["failed"] + sum(
        1 for target in targets
        for check in target.get("checks") or []
        if check.get("hard") and check.get("status") == "fail"
    )
    return {"ready": tally["ready"], "repaired": tally["repaired"],
            "advisory": advisory, "failed": failed}


def render_board_html(job_dir: Path, manifest: dict, inline: bool, cache: dict) -> str:
    base_dir = job_dir
    job_id = manifest.get("job", "job")
    job_name = manifest.get("job", "Review board")
    created = manifest.get("created", "")
    targets = manifest.get("targets") or []
    tally = target_status_tally(targets)
    chips = [
        ("Ready", tally["ready"]),
        ("Repaired", tally["repaired"]),
        ("Advisory", tally["advisory"]),
        ("Failed", tally["failed"]),
    ]
    parts = [HTML_HEAD.format(title=esc(job_name) + " - Postkitty review board", css=CSS)]
    parts.append(build_header(job_name, created, chips))
    parts.append('<div class="section">')
    parts.append(build_advice(manifest))
    grouped = group_targets(manifest)
    if grouped:
        for platform, targets_list in grouped:
            parts.append('<section class="platform-group">')
            parts.append(f'<h2>{esc(platform.title())}</h2>')
            parts.append('<div class="card-grid">')
            for target in targets_list:
                parts.append(build_target_card(target, manifest,
                                               manifest.get("alt_text") or {},
                                               inline, cache, job_id, base_dir))
            parts.append('</div>')
            parts.append('</section>')
    else:
        parts.append('<p class="empty">No targets yet.</p>')
    parts.append('</div>')
    parts.append(_script())
    parts.append("\n</body>\n</html>")
    return "".join(parts)


def _script() -> str:
    return """\
<script>
(function () {
  var toast = document.getElementById("pk-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "pk-toast";
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  function show(message) {
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(function () { toast.classList.remove("show"); }, 2500);
  }
  document.body.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy-caption]");
    if (button) {
      event.preventDefault();
      navigator.clipboard.writeText(button.getAttribute("data-copy-caption")).then(function () {
        show("Caption copied.");
      });
      return;
    }
    button = event.target.closest("[data-hermes-send]");
    if (button) {
      event.preventDefault();
      var prompt = button.getAttribute("data-hermes-send");
      var container = button.closest(".actions");
      var status = container ? container.querySelector(".hermes-status") : null;
      if (window.hermes && typeof window.hermes.send === "function") {
        if (status) status.textContent = "Sending to Hermes...";
        window.hermes.send(prompt).then(function (result) {
          if (status) status.textContent = "Sent. " + String(result);
        }).catch(function () {
          if (status) status.textContent = "Send failed.";
        });
      } else {
        navigator.clipboard.writeText(prompt).then(function () {
          show("Copied. Paste it to Hermes.");
          if (status) status.textContent = "Copied to clipboard.";
        });
      }
      return;
    }
    button = event.target.closest("[data-toggle-safe-area]");
    if (button) {
      event.preventDefault();
      var area = button.closest(".frame-wrap").querySelector(".safe-area");
      if (area) {
        area.classList.toggle("show");
        button.textContent = area.classList.contains("show") ? "Hide safe area" : "Show safe area";
      }
    }
  });
})();
</script>
"""


def write_contact_png(job_dir: Path, manifest: dict, mark_path: Path) -> Path:
    targets = manifest.get("targets") or []
    job_name = manifest.get("job", "Review board")
    created = manifest.get("created", "")
    width = 1600
    gap = 24
    margin = 40
    cols = 3 if targets else 1
    tile_w = (width - 2 * margin - (cols - 1) * gap) // cols
    mark_size = 40

    def thumb_box(aspect: float) -> tuple[int, int]:
        max_h = 240
        h = min(max_h, tile_w * aspect)
        w = h / aspect if aspect else tile_w
        return int(w), int(h)

    rows = 0
    row_heights: list[int] = []
    index = 0
    while index < len(targets):
        row_max = 0
        for _ in range(min(cols, len(targets) - index)):
            target = targets[index]
            aspect = 1.0
            try:
                aspect = int(target.get("width") or 0) / int(target.get("height") or 1) or 1.0
            except (TypeError, ValueError, ZeroDivisionError):
                aspect = 1.0
            w, h = thumb_box(aspect)
            row_max = max(row_max, h + 104)
            index += 1
        row_heights.append(row_max)
        rows += 1

    title_h = 120
    height = (title_h + gap + sum(row_heights) + (rows - 1) * gap + 60) if rows else (title_h + 80)
    image = Image.new("RGB", (width, height), CREAM)
    draw = ImageDraw.Draw(image)

    font_job = ImageFont.load_default(size=22)
    font_small = ImageFont.load_default(size=16)
    font_badge = ImageFont.load_default(size=15)

    mark = None
    if mark_path.is_file():
        try:
            mark = Image.open(mark_path).convert("RGBA")
        except Exception:
            mark = None

    cx = margin
    if mark is not None:
        mark_s = mark.resize((mark_size, mark_size), Image.LANCZOS)
        image.paste(mark_s, (cx, (title_h - mark_size) // 2), mark_s)
        cx += mark_size + 16
    draw.text((cx, 30), str(job_name), font=font_job, fill=NAVY)
    draw.text((cx, 64), str(created), font=font_small, fill=MUTED)

    y = title_h + gap
    index = 0
    for row_h in row_heights:
        x = margin
        row_targets = targets[index:index + cols]
        index += len(row_targets)
        for target in row_targets:
            kind = target.get("kind")
            aspect = 1.0
            try:
                aspect = int(target.get("width") or 0) / int(target.get("height") or 1) or 1.0
            except (TypeError, ValueError, ZeroDivisionError):
                aspect = 1.0
            tw, th = thumb_box(aspect)
            tx = x + (tile_w - tw) // 2
            card_bg = SURFACE
            draw.rounded_rectangle([x, y, x + tile_w, y + row_h], radius=12, fill=card_bg, outline=BORDER, width=1)
            thumb = None
            file_rel = target.get("file") or ""
            cover_rel = target.get("cover")
            source = cover_rel if kind == "video" and cover_rel else file_rel
            full_source = job_dir / source if source and not os.path.isabs(source) \
                else Path(source)
            if source and full_source.is_file():
                try:
                    with Image.open(full_source) as img:
                        img = ImageOps_exif_transpose(img).convert("RGB")
                        img.thumbnail((tw, th), Image.LANCZOS)
                        thumb = img
                except Exception:
                    thumb = None
            if thumb is not None:
                image.paste(thumb, (tx, y + 14))
            else:
                draw.rounded_rectangle([tx, y + 14, tx + tw, y + 14 + th], radius=8, fill="#1E2A44")
                draw.text((tx + 6, y + 14 + th / 2 - 8), "media", font=font_small, fill="#F7F1E5")
            ly = y + 14 + th + 12
            draw.text((x + 12, ly), str(target.get("platform", "")).title(), font=font_badge, fill=NAVY)
            draw.text((x + 12, ly + 20), str(target.get("id", "")), font=font_small, fill=MUTED)
            size_text = f"{int(target.get('width') or 0)}x{int(target.get('height') or 0)}"
            dur = format_duration(target.get("duration"))
            meta = size_text + (f"  {dur}" if dur else "")
            draw.text((x + 12, ly + 40), meta, font=font_small, fill=MUTED)
            status = str(target.get("status", "unknown"))
            color = STATUS_COLORS.get(status, "#5B6478")
            label = STATUS_LABELS.get(status, status)
            bw = draw.textlength(label, font=font_badge) + 16
            draw.rounded_rectangle([x + 12, ly + 64, x + 12 + bw, ly + 64 + 22], radius=11, fill=color)
            draw.text((x + 20, ly + 68), label, font=font_badge, fill="#FFFFFF")
            x += tile_w + gap
        y += row_h + gap
    out_path = job_dir / "contact.png"
    image.save(out_path, format="PNG", optimize=True)
    return out_path


def render_inline_level(job_dir: Path, manifest: dict, cache: dict, max_side: int,
                        quality: int, drop_duplicates: bool,
                        drop_all_posters: bool) -> tuple[str, int]:
    """Render one inline board variant; return (html, byte size)."""
    base_dir = job_dir
    job_id = manifest.get("job", "job")
    job_name = manifest.get("job", "Review board")
    created = manifest.get("created", "")
    targets = manifest.get("targets") or []
    tally = target_status_tally(targets)
    chips = [
        ("Ready", tally["ready"]),
        ("Repaired", tally["repaired"]),
        ("Advisory", tally["advisory"]),
        ("Failed", tally["failed"]),
    ]
    parts = [HTML_HEAD.format(
        title=esc(job_name) + " - Postkitty review board (inline)", css=CSS)]
    parts.append(build_header(job_name, created, chips))
    parts.append('<div class="section">')
    parts.append(build_advice(manifest))
    grouped = group_targets(manifest)
    if grouped:
        seen_posters: set[str] = set()
        for platform, targets_list in grouped:
            parts.append('<section class="platform-group">')
            parts.append(f'<h2>{esc(platform.title())}</h2>')
            parts.append('<div class="card-grid">')
            for target in targets_list:
                kind = target.get("kind")
                cover_rel = target.get("cover")
                if drop_all_posters or (kind == "video" and cover_rel
                                        and os.path.abspath(str(cover_rel)) in seen_posters):
                    target = dict(target)
                    target["cover"] = None
                parts.append(build_target_card(target, manifest,
                                               manifest.get("alt_text") or {},
                                               True, cache, job_id, base_dir, max_side,
                                               quality))
                if cover_rel and kind == "video" and not drop_all_posters:
                    seen_posters.add(os.path.abspath(str(job_dir / cover_rel)))
            parts.append('</div>')
            parts.append('</section>')
    else:
        parts.append('<p class="empty">No targets yet.</p>')
    parts.append('</div>')
    parts.append('<div class="visually-hidden">Inline board: self-contained preview, no file access.</div>')
    parts.append(_script())
    parts.append("\n</body>\n</html>")
    html_text = "".join(parts)
    return html_text, len(html_text.encode("utf-8"))


def render_inline_html(job_dir: Path, manifest: dict, cache: dict) -> tuple[str, int]:
    """Same design as board.html, fully self-contained with data URIs.

    Honors the 6 MB cap: start at JPEG 720 px / quality 80, fall back to
    480 px / quality 70, then drop posters for duplicates, then drop all
    posters. Returns the final variant and its byte size.
    """
    levels = [
        (720, 80, False, False),
        (480, 70, False, False),
        (480, 70, True, False),
        (480, 70, True, True),
    ]
    html_text = ""
    inline_size = 0
    for max_side, quality, drop_duplicates, drop_all_posters in levels:
        # Re-render with per-level image parameters by wrapping cache keys.
        html_text, inline_size = render_inline_level(job_dir, manifest, cache, max_side,
                                                     quality, drop_duplicates,
                                                     drop_all_posters)
        if inline_size <= 6 * 1024 * 1024:
            break
    return html_text, inline_size


def write_board(job_dir: Path, manifest: dict) -> dict:
    """Writes board.html, board-inline.html and contact.png into job_dir.

    Returns a dict with absolute paths for board, board_inline and contact,
    plus board_inline_size (final byte size of the inlined board).
    """
    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    mark_path = here / "templates" / "possy-mark-64.png"

    cache: dict = {}

    board_html = render_board_html(job_dir, manifest, False, cache)
    board_path = job_dir / "board.html"
    board_path.write_text(board_html, encoding="utf-8")

    contact_path = write_contact_png(job_dir, manifest, mark_path)

    inline_html, inline_size = render_inline_html(job_dir, manifest, cache)
    inline_path = job_dir / "board-inline.html"
    inline_path.write_text(inline_html, encoding="utf-8")

    return {
        "board": str(board_path.resolve()),
        "board_inline": str(inline_path.resolve()),
        "contact": str(contact_path.resolve()),
        "board_inline_size": inline_size,
    }
