def calculate_routine_timer(
    total_minutes: int,
    num_steps: int,
    current_tokens: int = 0,
    target_tokens: int = 5,
) -> str:
    """Calculates visual step durations, break intervals, and token reward progress for a social story routine.

    Args:
        total_minutes: Total allocated time for the routine (e.g., 15 minutes).
        num_steps: Number of steps in the social story (e.g., 3 steps).
        current_tokens: Current number of reward tokens earned so far.
        target_tokens: Target tokens needed to unlock reward (default 5).

    Returns:
        Formatted summary with minutes per step, break guidance, and token progress.
    """
    if num_steps <= 0:
        return "Error: Number of steps must be at least 1."

    minutes_per_step = round(total_minutes / num_steps, 1)
    tokens_needed = max(0, target_tokens - current_tokens)
    progress_pct = min(100, round((current_tokens / target_tokens) * 100))

    summary = [
        f"⏱️ Routine Timing Breakdown:",
        f"- Total Allocated Time: {total_minutes} minutes",
        f"- Time Per Step: ~{minutes_per_step} minutes across {num_steps} steps",
        f"- Recommended Sensory Break: 1-minute calm breather between steps",
        f"",
        f"🌟 Token Economy Reward Tracker:",
        f"- Tokens Earned: {current_tokens}/{target_tokens} ({progress_pct}%)",
    ]

    if tokens_needed > 0:
        summary.append(f"- Tokens Remaining: {tokens_needed} more token(s) needed for prize reward!")
    else:
        summary.append("🎉 Reward Unlocked! Great job completing the routine!")

    return "\n".join(summary)
