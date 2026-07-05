from app.services.threads_terminal_service import explain_rider_gate, session_panel


def test_explain_rider_gate_accepts_direct_evidence():
    text = "Stuck at Bangsar on Kelana Jaya line for 25 min already, train not moving"
    result = explain_rider_gate(text)
    assert result["accepted"] is True
    assert result["entity"]


def test_explain_rider_gate_rejects_grab_rant():
    text = "Minute tunggu grab lebih lama dari naik LRT, better mrt or lrt laju"
    result = explain_rider_gate(text)
    assert result["accepted"] is False


def test_session_panel_shape():
    panel = session_panel()
    assert "available" in panel
    assert "path" in panel
