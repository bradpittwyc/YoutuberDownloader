from types import SimpleNamespace
import tkinter as tk
from channel_gui import ChannelApp


def state(selected):
    return SimpleNamespace(busy=False, catalog=True, selected=set(selected),
                           entries={'a': None, 'b': None},
                           tree=SimpleNamespace(focus=lambda: 'a'),
                           refresh_checks=lambda: None)


def test_catalog_click_again_deselects():
    app = state(['a'])
    ChannelApp.toggle(app, SimpleNamespace(type=tk.EventType.KeyPress))
    assert app.selected == set()


def test_catalog_select_other_replaces_selection():
    app = state(['b'])
    ChannelApp.toggle(app, SimpleNamespace(type=tk.EventType.KeyPress))
    assert app.selected == {'a'}


def test_catalog_clear_selection():
    app = state(['a'])
    ChannelApp.select_all(app, False)
    assert app.selected == set()
