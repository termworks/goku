"""Versioned optical icon policy derived from Goku 1.100 measurements.

Generate the supporting reports with ``make icon-policy``. These are the only
icons that safely exceeded the p95 bounding size of their source/aspect/circular
class by the P1.3 visual threshold. Scaling is uniform, never enlarges an icon,
and is applied around the center of the terminal cell.
"""

from __future__ import annotations


POLICY_BASELINE_SHA256 = (
    "b784156edd9c1cef9fa85a3e93db74d20b637c2b63956659d2eb7460e5eb2d62"
)

OPTICAL_SCALE_BY_CODEPOINT = {
    0xE348: 0.857771,  # Weather Icons: uniF04C
    0xE34A: 0.844248,  # Weather Icons: uniF04E
    0xE35C: 0.915493,  # Weather Icons: uniF062
    0xE3BF: 0.875748,  # Weather Icons: uniF0C7
    0xE3C0: 0.816781,  # Weather Icons: uniF0C8
    0xEBC5: 0.934156,  # Codicons: terminal-debian
    0xED10: 0.922758,  # Font Awesome: nutritionix
    0xED14: 0.917695,  # Font Awesome: periscope
    0xED63: 0.929166,  # Font Awesome: chess_knight
    0xED66: 0.915184,  # Font Awesome: chess_rook
    0xEDA5: 0.930459,  # Font Awesome: ribbon
    0xEF0C: 0.924671,  # Font Awesome: person_running
    0xEF80: 0.915184,  # Font Awesome: egg
    0xF17C: 0.940267,  # Font Awesome: linux.1
    0xF18D: 0.922758,  # Font Awesome: stack_exchange
    0xF210: 0.915184,  # Font Awesome: dashcube
    0xF28A: 0.927234,  # Font Awesome: scribd
    0xF2A6: 0.929166,  # Font Awesome: glide_g
    0xF2F2: 0.929166,  # Font Awesome: stopwatch
}
