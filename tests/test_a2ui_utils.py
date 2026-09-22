from app.a2ui_utils import a2ui_callback

def test_a2ui_callback_none():
    res = a2ui_callback(None, None)
    assert res is None
