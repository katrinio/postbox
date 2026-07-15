from postbox.keyboards.main_menu import MainMenuAction, main_menu_keyboard


def test_main_menu_contains_every_action() -> None:
    keyboard = main_menu_keyboard()

    labels = [button.text for row in keyboard.keyboard for button in row]

    assert labels == [
        MainMenuAction.SEND,
        MainMenuAction.RECEIVE,
        MainMenuAction.JOURNAL,
    ]
    assert keyboard.is_persistent is True
