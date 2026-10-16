from bearing.question_test import auto_check


def test_auto_check():
    assert auto_check("I don’t know that from this data.", must_decline=True)
    assert not auto_check("It will fail in 3 days.", must_decline=True)
    assert auto_check("Check the bearing with a vibration check.", must_decline=False)
    assert not auto_check("About 80% likely, fails in 2 days.", must_decline=False)
