from django.core.management import call_command
import pytest
from easyimap import easyimap

from adjuntos.models import Email, Attachment
from elecciones.tests.factories import get_random_image


def test_importar_actas_desde_email_unseen(settings, db, mocker):
    settings.IMAPS = [
        {
            "email": "actas@gmail.com",
            "host": "imap.gmail.com",
            "user": "actas",
            "pass": "xxxx",
            "mailbox": "INBOX",
        },
        {
            "email": "actas2@elecciones.com",
            "host": "imap.elecciones.com",
            "user": "actas2",
            "pass": "xxxx",
            "mailbox": "CUSTOM_INBOX",
        },
    ]
    connect = mocker.patch(
        "adjuntos.management.commands.importar_actas_desde_email.easyimap.connect"
    )
    mails_account_1 = [
        mocker.Mock(
            easyimap.MailObj,
            body="body",
            title="title",
            date="date",
            from_addr="from_addr",
            uid=1,
            message_id=1,
            attachments=[
                (
                    "acta1.jpg",
                    get_random_image().getvalue(),
                    "image/jpeg",
                )
            ],
        )
    ]
    mails_account_2 = [
        mocker.Mock(
            easyimap.MailObj,
            body="body 2",
            title="title 2",
            date="date 2",
            from_addr="from_addr 2",
            uid=2,
            message_id=2,
            attachments=[
                (
                    "acta2.jpg",
                    get_random_image().getvalue(),
                    "image/jpeg",
                ),
                (
                    "acta3.jpg",
                    get_random_image().getvalue(),
                    "image/jpeg",
                ),
            ],
        )
    ]

    connect.return_value.unseen.side_effect = [mails_account_1, mails_account_2]
    call_command("importar_actas_desde_email")

    assert connect.call_args_list == [
        mocker.call("imap.gmail.com", "actas", "xxxx", "INBOX"),
        mocker.call("imap.elecciones.com", "actas2", "xxxx", "CUSTOM_INBOX"),
    ]
    assert Email.objects.count() == 2
    assert Attachment.objects.count() == 3


@pytest.mark.skip(reason="TO DO")
def test_importar_actas_desde_email_include_seen(settings, db, mocker):
    pass



@pytest.mark.skip(reason="TO DO")
def test_importar_actas_desde_email_only_images(settings, db, mocker):
    pass

