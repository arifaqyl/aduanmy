from app.pipeline.normalize import normalize_text
from app.pipeline.extract import category_signal_ok, detect_language_mix, detect_severity, extract_entity, extract_issue_key, extract_location
from app.services.ingest_service import build_cluster_id


def test_normalize_text_collapses_spaces() -> None:
    assert normalize_text("  unifi   tak   boleh  ") == "unifi tak boleh"


def test_detect_language_mix_rojak() -> None:
    assert detect_language_mix("unifi tak boleh login") == "rojak"


def test_detect_severity_high() -> None:
    assert detect_severity("duitnow down tak boleh pakai") == "high"


def test_extract_location() -> None:
    assert extract_location("lrt rosak dekat kl sentral pagi tadi") == "KL Sentral"


def test_extract_location_transport_station_variant() -> None:
    assert extract_location("tak boleh keluar stesen sebab fire alarm kat mrt maluri") == "Maluri"


def test_extract_location_prefers_actual_station_over_line_name() -> None:
    text = "Kelewatan Tren Laluan Kelana Jaya. Bas perantara ulang-alik percuma disediakan di antara Bangsar dan KL Gateway."
    assert extract_location(text) == "KL Gateway"


def test_extract_location_supports_chan_sow_lin_and_ara_damansara() -> None:
    assert extract_location("train derails near chan sow lin station") == "Chan Sow Lin"
    assert extract_location("kelana jaya lrt line delays at ara damansara station") == "Ara Damansara"


def test_extract_location_supports_dang_wangi() -> None:
    assert extract_location("train stopped abruptly near dang wangi station during kelana jaya line incident") == "Dang Wangi"


def test_extract_location_supports_pasar_seni() -> None:
    assert extract_location("train at pasar seni station is being manually operated due to a door malfunction") == "Pasar Seni"


def test_extract_location_supports_more_current_mrt_stations() -> None:
    assert extract_location("mrt putrajaya problem guysss at kepong baru") == "Kepong Baru"
    assert extract_location("MRT problem, everyone stuck in Semantan") == "Semantan"
    assert extract_location("kena turun chan sow lin then tukar dekat masjid jamek") == "Masjid Jamek"


def test_extract_location_does_not_treat_line_name_as_station() -> None:
    assert extract_location("Kemas Kini Laluan Ampang/Sri Petaling") == ""


def test_extract_entity_prefers_specific_transport_line_over_generic_lrt() -> None:
    text = "Services on the Ampang and Sri Petaling LRT Lines are experiencing a disruption following a track switch failure."
    assert extract_entity(text, "transport") == "Ampang/Sri Petaling Line"


def test_extract_entity_supports_malay_line_wording() -> None:
    text = "Kelewatan Tren Laluan Kelana Jaya. Bas perantara ulang-alik percuma disediakan di antara Bangsar dan KL Gateway."
    assert extract_entity(text, "transport") == "Kelana Jaya Line"


def test_extract_entity_supports_lrt_and_mrt_line_variants() -> None:
    assert extract_entity("Commuters on the Kelana Jaya LRT Line experienced delays this morning.", "transport") == "Kelana Jaya Line"
    assert extract_entity("MRT Kajang Line delay near Pasar Seni today", "transport") == "Kajang Line"


def test_extract_entity_supports_multi_line_mrt_wording() -> None:
    text = "Delays on Putrajaya, Kajang MRT lines due to brake failures"
    assert extract_entity(text, "transport") == "Kajang/Putrajaya Lines"


def test_category_signal_ok_rejects_telco_entertainment_noise() -> None:
    text = "hbo channels stopped broadcasting on astro and may be pulled from unifi tv later"
    assert not category_signal_ok(text, "telco_internet", "Unifi")


def test_category_signal_ok_rejects_generic_immigration_life_post() -> None:
    text = "abusive marriage and immigration lawyers keep giving different visa advice"
    assert not category_signal_ok(text, "gov_portals", "Immigration")


def test_category_signal_ok_rejects_generic_bank_account_advice() -> None:
    text = "need advice on opening a maybank business account from abroad"
    assert not category_signal_ok(text, "banking_payments", "Maybank")


def test_category_signal_ok_rejects_grab_evp_admin_post() -> None:
    text = "grab evp renewal is terrible and i cannot get my e-hailing vehicle permit sorted"
    assert not category_signal_ok(text, "gov_portals", "MyJPJ")


def test_category_signal_ok_rejects_property_rant_with_incidental_unifi() -> None:
    text = "i am a property owner dealing with gsd land and post-vp problems, including unifi home internet issues"
    assert not category_signal_ok(text, "telco_internet", "Unifi")


def test_category_signal_ok_rejects_telco_ekyc_rant() -> None:
    text = "celcomdigi app asked for id check and facial verification then said face not valid and cooldown timer"
    assert not category_signal_ok(text, "telco_internet", "CelcomDigi")


def test_extract_issue_key_transport_incident() -> None:
    text = "lrt kelana jaya line is experiencing an incident and help and rescue is mobilising"
    assert extract_issue_key(text, "transport") == "incident"


def test_extract_issue_key_transport_technical_fault() -> None:
    text = "delays on putrajaya, kajang mrt lines due to brake failures"
    assert extract_issue_key(text, "transport") == "technical_fault"


def test_extract_issue_key_transport_delay_supports_rojak_stoppage_language() -> None:
    text = "mrt kajang line problem ke? kenape tak gerak2 ni"
    assert extract_issue_key(text, "transport") == "delay"


def test_extract_issue_key_transport_delay_supports_having_problems_wording() -> None:
    text = "LRT Kelana Jaya line having problems again this morning"
    assert extract_issue_key(text, "transport") == "delay"


def test_category_signal_ok_accepts_malay_transport_disruption_wording() -> None:
    text = "rapid kl masalah sistem kawalan tren automatik jejas perkhidmatan lrt laluan kelana jaya di kuala lumpur"
    assert category_signal_ok(text, "transport", "LRT")


def test_category_signal_ok_accepts_current_rojak_mrt_delay_language() -> None:
    text = "Korang Mrt Kajang line problem ke? kenape tak gerak2 ni..."
    assert category_signal_ok(text, "transport", "Kajang Line")


def test_build_cluster_id_prefers_entity_and_location() -> None:
    assert build_cluster_id("transport", "LRT", "Kelana Jaya", "incident", "x") == "transport:LRT:Kelana Jaya:incident"


def test_build_cluster_id_falls_back_to_issue_when_no_location() -> None:
    assert build_cluster_id("telco_internet", "Unifi", "", "outage", "reddit") == "telco_internet:Unifi:outage"
