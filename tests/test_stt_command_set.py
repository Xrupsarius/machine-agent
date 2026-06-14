from app.stt.command_set import CommandSet


def _ru():
    return CommandSet.from_config("ru")


def _en():
    return CommandSet.from_config("en")


def test_plain_text_no_command():
    body, local, agent = _ru().parse("привет мир как дела")
    assert (local, agent) == (None, None)
    assert body == "привет мир как дела"


def test_marker_submit():
    body, local, agent = _ru().parse("привет мир омнис отправь")
    assert local == "submit" and agent is None
    assert body == "привет мир"


def test_marker_split_by_stt():
    # Whisper splits «омнис» into «омни с»
    body, local, _ = _ru().parse("текст омни с отправь")
    assert local == "submit"
    assert body == "текст"


def test_marker_variants_tolerated():
    for phrase in ["омнись отправь", "омнес отправь", "амнис отправь"]:
        assert _ru().parse(phrase)[1] == "submit", phrase


def test_newline_and_delete_and_stop():
    assert _ru().parse("омнис новая строка")[1] == "newline"
    assert _ru().parse("омнис сатри")[1] == "delete_word"
    assert _ru().parse("омнис сотри последнее")[1] == "delete_word"
    assert _ru().parse("омнис стоп")[1] == "stop"


def test_agent_command_routed():
    body, local, agent = _ru().parse("заметка омнис открой браузер")
    assert local is None
    assert agent == "открой браузер"
    assert body == "заметка"


def test_normal_speech_does_not_trigger_marker():
    for phrase in ["я приготовил омлет на завтрак", "это очень хороший омут", "новая строка кода"]:
        _, local, agent = _ru().parse(phrase)
        assert (local, agent) == (None, None), phrase


def test_english_commands():
    en = _en()
    assert en.parse("hello world omnis send")[1] == "submit"
    assert en.parse("omnis new line")[1] == "newline"
    assert en.parse("note omnis open browser")[2] == "open browser"


def test_from_config_falls_back_when_file_missing():
    cs = CommandSet.from_config("ru", path="/nonexistent/commands.yaml")
    assert cs.parse("омнис отправь")[1] == "submit"


def test_language_attribute():
    assert _en().language == "en"
    assert _ru().language == "ru"
