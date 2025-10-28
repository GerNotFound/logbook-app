import pytest

from utils import generate_avatar_color, is_valid_time_format


@pytest.mark.parametrize(
    'time_str, expected',
    [
        ('00:00', True),
        ('23:59', True),
        ('7:30', True),
        ('24:00', False),
        ('12:60', False),
        ('', True),
        (None, True),
    ],
)
def test_is_valid_time_format(time_str, expected):
    assert is_valid_time_format(time_str) is expected


def test_generate_avatar_color_is_deterministic():
    color_one = generate_avatar_color(10)
    color_two = generate_avatar_color(10)
    assert color_one == color_two


def test_generate_avatar_color_falls_back_for_none():
    fallback_color = generate_avatar_color(None)
    assert isinstance(fallback_color, str)
    assert fallback_color.startswith('#')


@pytest.mark.parametrize('user_id', [1, 2, 3, 100, -7])
def test_generate_avatar_color_palette_bounds(user_id):
    color = generate_avatar_color(user_id)
    assert color.startswith('#')
    assert len(color) in (4, 7)
