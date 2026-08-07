from scripts.check_sensitive_identifiers import scan_text


def test_rejects_account_conversation_and_message_identifiers():
    account_id = "221" + "4350705775"
    conversation_id = "605" + "85751957"
    message_id = "407" + "71518" + "26249.PNM"
    text = "\n".join(
        [
            f'{{"unb":"{account_id}"}}',
            f'{{"cid":"{conversation_id}"}}',
            f'{{"msg_ids":["{message_id}"]}}',
            f'goofish message send {conversation_id} {account_id} --text hello',
            f'_make_cookie("unb", "{account_id}", ".taobao.com")',
            f'generate_device_id("{account_id}")',
        ]
    )

    findings = scan_text(text)

    assert {line for line, _ in findings} == {1, 2, 3, 4, 5, 6}


def test_allows_masked_values_fake_fixtures_and_public_item_ids():
    text = "\n".join(
        [
            '{"unb":"<masked-unb>","tracknick":"<masked-tracknick>"}',
            '{"cid":"test-cid","send_user_id":"test-user"}',
            "goofish item get 1045171414271",
        ]
    )

    assert scan_text(text) == []
