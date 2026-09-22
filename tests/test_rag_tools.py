from app.rag_tools import consult_ot_guidance

def test_consult_ot_guidance_dentist():
    res = consult_ot_guidance("dentist visit preparation")
    assert "Dental Visits" in res or "Carol Gray" in res

def test_consult_ot_guidance_fallback():
    res = consult_ot_guidance("general bedtime routine")
    assert "Occupational Therapy" in res
