from ws.template_editor import _highlight_match, _summarize_preview_items


def test_highlight_match_prefix_case_insensitive():
    assert _highlight_match('Rematore Bilanciere', 're').startswith('<mark>Re</mark>')
    assert '<mark>re</mark>' not in _highlight_match('Rematore Bilanciere', 're')


def test_highlight_match_escapes_html():
    highlighted = _highlight_match('Push <Pull>', 'pull')
    assert highlighted == 'Push &lt;<mark>Pull</mark>&gt;'


def test_highlight_match_without_match_returns_escaped():
    assert _highlight_match('Panca Piana', 'xyz') == 'Panca Piana'


def test_summarize_preview_items_counts_exercises_and_sets():
    summary = _summarize_preview_items([
        {'sets': 4},
        {'sets': '3'},
        {'sets': -2},
        {'sets': 'invalid'},
    ])
    assert summary == {'total_exercises': 3, 'total_sets': 7}
