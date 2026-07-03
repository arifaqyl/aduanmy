from app.pipeline.geo import infer_state
from app.pipeline.extract import extract_location


def test_infer_state_from_jb_sentral_text():
    loc = extract_location("ktm komuter delay at jb sentral this morning")
    assert loc == "JB Sentral"
    assert infer_state(text="ktm komuter delay at jb sentral", location=loc, entity="KTM", category="transport") == "Johor"


def test_infer_state_from_penang():
    assert infer_state(text="rapid penang bas rosak di butterworth", location="Butterworth", entity="Penang Rapid", category="transport") == "Penang"


def test_infer_state_from_klang_valley_line():
    assert infer_state(text="kelana jaya line delay", location="", entity="Kelana Jaya Line", category="transport") == "Selangor"


def test_infer_state_from_sabah():
    assert infer_state(text="bas rosak di kota kinabalu pagi tadi", location="", entity="", category="transport") == "Sabah"
