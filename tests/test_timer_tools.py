from app.timer_tools import calculate_routine_timer

def test_calculate_routine_timer():
    res = calculate_routine_timer(total_minutes=15, num_steps=3, current_tokens=2)
    assert "Time Per Step: ~5.0 minutes" in res
    assert "Tokens Earned: 2/5" in res
    assert "3 more token(s) needed" in res

def test_calculate_routine_timer_completed():
    res = calculate_routine_timer(total_minutes=10, num_steps=2, current_tokens=5)
    assert "Reward Unlocked!" in res
