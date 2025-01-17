"""
File: message.py
----------------
This module contains the implementation of the Message object.

"""
import re
import base64
import json
import pathlib
import email as elib

from pathlib import PurePath
from datetime import datetime
from typing import List, Optional, Union

from httplib2 import Http
from googleapiclient.errors import HttpError

from simplegmail import label
from simplegmail.attachment import Attachment
from simplegmail.label import Label


class Message(object):
    """
    The Message class for emails in your Gmail mailbox. This class should not
    be manually constructed. Contains all information about the associated
    message, and can be used to modify the message's labels (e.g., marking as
    read/unread, archiving, moving to trash, starring, etc.).

    Args:
        service: the Gmail service object.
        user_id: the username of the account the message belongs to.
        msg_id: the message id.
        thread_id: the thread id.
        recipient: who the message was addressed to.
        sender: who the message was sent from.
        subject: the subject line of the message.
        date: the date the message was sent.
        snippet: the snippet line for the message.
        plain: the plaintext contents of the message. Default None.
        html: the HTML contents of the message. Default None.
        label_ids: the ids of labels associated with this message. Default [].
        attachments: a list of attachments for the message. Default [].
        raw_response: the origin response from google API

    Attributes:
        _service (googleapiclient.discovery.Resource): the Gmail service object.
        user_id (str): the username of the account the message belongs to.
        id (str): the message id.
        recipient (str): who the message was addressed to.
        sender (str): who the message was sent from.
        subject (str): the subject line of the message.
        date (str): the date the message was sent.
        snippet (str): the snippet line for the message.
        plain (str): the plaintext contents of the message.
        html (str): the HTML contents of the message.
        label_ids (List[str]): the ids of labels associated with this message.
        attachments (List[Attachment]): a list of attachments for the message.

    """

    def __init__(
            self,
            service: "googleapiclient.discovery.Resource",
            creds: "oauth2client.client.OAuth2Credentials",
            user_id: str,
            msg_id: str,
            thread_id: str,
            recipient: str,
            sender: str,
            subject: str,
            date: str,
            snippet,
            plain: Optional[str] = None,
            html: Optional[str] = None,
            cc: Optional[str] = None,
            bcc: Optional[str] = None,
            label_ids: Optional[List[str]] = None,
            attachments: Optional[List[Attachment]] = None,
            headers: Optional[dict] = None,
            headers_list: Optional[list] = None,
            raw_response: Optional[dict] = None,
            raw_base64: Optional[str] = None,
    ) -> None:
        self._service = service
        self.creds = creds
        self.user_id = user_id
        self.id = msg_id
        self.thread_id = thread_id
        self.recipient = recipient
        self.sender = sender
        self.subject = subject
        self.cc = cc
        self.bcc = bcc
        self.date = datetime.fromisoformat(date)
        self.snippet = snippet
        self.plain = plain
        self.html = html
        self.label_ids = label_ids if label_ids is not None else []
        self.attachments = attachments if attachments is not None else []
        self.headers = headers if headers else {}
        self.headers_list = headers_list if headers_list else []
        self.raw_response = raw_response if raw_response else {}
        self.raw_base64 = raw_base64 if raw_base64 else None

    @property
    def service(self) -> "googleapiclient.discovery.Resource":
        if self.creds.access_token_expired:
            self.creds.refresh(Http())

        return self._service

    @classmethod
    def parse_raw_email(cls, content):
        email = content.decode()
        new_email = []
        for line in email.split("\n"):
            if to and line.startswith("To: "):
                new_email.append(f"To: {to}\r")
            elif sender and line.startswith("From: "):
                new_email.append(line)
                new_email.append(f"Reply-To: {sender}\r")
                new_email.append(f"Resent-To: {to}\r")
                new_email.append(f"On-Behalf-Of: {sender}\r")
            else:
                new_email.append(line)
        new_email_b = "\n".join(new_email).encode()
        return base64.urlsafe_b64encode(new_email_b).decode()



    def __repr__(self) -> str:
         """Represents the object by its sender, recipient, and id."""

         return f"Message(to: {self.recipient}, from: {self.sender}, id: {self.id})"

    def get_std_msg(self) -> elib.message.Message:
        if not self.raw_base64:
            raise ValueError("missing raw_base64 field")
        email = base64.urlsafe_b64decode(self.raw_base64)
        return elib.message_from_bytes(email, policy=elib.policy.default)

    def as_string(self, with_header=False) -> str:
        return self.get_std_msg().as_string(unixfrom=with_header, maxheaderlen=0)

    def as_simple_string(self, headers=["from", "to", "cc", "bcc", "subject"]) -> str:
        res = []
        message = self.get_std_msg()
        for h in headers:
            res.append(f"{h}: {message[h]}")
        body = message.get_body()
        res.append("\n\n" + body.get_content())
        return "\n".join(res)

    def forward_body(self, to: str, sender: str) -> str:
        """return ready to sent forward message"""
        msg = self.get_std_msg()
        msg.replace_header("To", to)
        msg.add_header("Resent-To", to)
        msg.add_header("Reply-To", sender)
        msg.add_header("On-Behalf-Of", sender)
        new_email_b = msg.as_bytes()
        return base64.urlsafe_b64encode(new_email_b).decode()

    def download_attachments(self, overwrite: bool = True, tmpdir="/tmp"):
        dest_dir = str(PurePath().joinpath(tmpdir, self.id, "attachments"))
        pathlib.Path(dest_dir).mkdir(parents=True, exist_ok=True)
        paths = []
        for attach in self.attachments:
            fpath = PurePath().joinpath(
                dest_dir,
                f"{attach.filename}",
            )
            attach.save(str(fpath), overwrite)
            paths.append(str(fpath))
        return paths

    def mark_as_read(self) -> None:
        """
        Marks this message as read (by removing the UNREAD label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.UNREAD)

    def mark_as_unread(self) -> None:
        """
        Marks this message as unread (by adding the UNREAD label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_label(label.UNREAD)

    def mark_as_spam(self) -> None:
        """
        Marks this message as spam (by adding the SPAM label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_label(label.SPAM)

    def mark_as_not_spam(self) -> None:
        """
        Marks this message as not spam (by removing the SPAM label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.SPAM)

    def mark_as_important(self) -> None:
        """
        Marks this message as important (by adding the IMPORTANT label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_label(label.IMPORTANT)

    def mark_as_not_important(self) -> None:
        """
        Marks this message as not important (by removing the IMPORTANT label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.IMPORTANT)

    def star(self) -> None:
        """
        Stars this message (by adding the STARRED label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_label(label.STARRED)

    def unstar(self) -> None:
        """
        Unstars this message (by removing the STARRED label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.STARRED)

    def move_to_inbox(self) -> None:
        """
        Moves an archived message to your inbox (by adding the INBOX label).

        """

        self.add_label(label.INBOX)

    def archive(self) -> None:
        """
        Archives the message (removes from inbox by removing the INBOX label).

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_label(label.INBOX)

    def trash(self) -> None:
        """
        Moves this message to the trash.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        try:
            res = (
                self._service.users()
                .messages()
                .trash(
                    userId=self.user_id,
                    id=self.id,
                )
                .execute()
            )

        except HttpError as error:
            # Pass error along
            raise error

        else:
            assert (
                label.TRASH in res["labelIds"]
            ), f"An error occurred in a call to `trash`."

            self.label_ids = res["labelIds"]

    def text_headers(self) -> str:
        headers = []
        for header in self.headers_list:
            headers.append(f"{header['name']}: {header['value']}")
        return "\n".join(headers)

    def untrash(self) -> None:
        """
        Removes this message from the trash.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        try:
            res = (
                self._service.users()
                .messages()
                .untrash(
                    userId=self.user_id,
                    id=self.id,
                )
                .execute()
            )

        except HttpError as error:
            # Pass error along
            raise error

        else:
            assert (
                label.TRASH not in res["labelIds"]
            ), f"An error occurred in a call to `untrash`."

            self.label_ids = res["labelIds"]

    def move_from_inbox(self, to: Union[Label, str]) -> None:
        """
        Moves a message from your inbox to another label "folder".

        Args:
            to: The label to move to.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.modify_labels(to, label.INBOX)

    def add_label(self, to_add: Union[Label, str]) -> None:
        """
        Adds the given label to the message.

        Args:
            to_add: The label to add.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.add_labels([to_add])

    def add_labels(self, to_add: Union[List[Label], List[str]]) -> None:
        """
        Adds the given labels to the message.

        Args:
            to_add: The list of labels to add.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.modify_labels(to_add, [])

    def json(self, indent: int = 4):
        """Returns the original response from Google as Json"""
        if self.raw_base64:
            self.raw_response['raw'] = self.raw_base64
        return json.dumps(self.raw_response, indent=indent)

    def dump(self, filepath: str, as_string=False):
        pathlib.Path(pathlib.PurePath(filepath).parent).mkdir(
            parents=True, exist_ok=True
        )
        with open(filepath, "w") as fname:
            if as_string:
                fname.write(self.as_string())
            else:
                fname.write(self.json())
        return filepath

    def remove_label(self, to_remove: Union[Label, str]) -> None:
        """
        Removes the given label from the message.

        Args:
            to_remove: The label to remove.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.remove_labels([to_remove])

    def remove_labels(self, to_remove: Union[List[Label], List[str]]) -> None:
        """
        Removes the given labels from the message.

        Args:
            to_remove: The list of labels to remove.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        self.modify_labels([], to_remove)

    def modify_labels(
        self,
        to_add: Union[Label, str, List[Label], List[str]],
        to_remove: Union[Label, str, List[Label], List[str]],
    ) -> None:
        """
        Adds or removes the specified label.

        Args:
            to_add: The label or list of labels to add.
            to_remove: The label or list of labels to remove.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        if isinstance(to_add, (Label, str)):
            to_add = [to_add]

        if isinstance(to_remove, (Label, str)):
            to_remove = [to_remove]

        try:
            res = (
                self._service.users()
                .messages()
                .modify(
                    userId=self.user_id,
                    id=self.id,
                    body=self._create_update_labels(to_add, to_remove),
                )
                .execute()
            )

        except HttpError as error:
            # Pass along error
            raise error

        else:
            assert all([lbl in res["labelIds"] for lbl in to_add]) and all(
                [lbl not in res["labelIds"] for lbl in to_remove]
            ), "An error occurred while modifying message label."

            self.label_ids = res["labelIds"]

    def _create_update_labels(
        self,
        to_add: Union[List[Label], List[str]] = None,
        to_remove: Union[List[Label], List[str]] = None,
    ) -> dict:
        """
        Creates an object for updating message label.

        Args:
            to_add: A list of labels to add.
            to_remove: A list of labels to remove.

        Returns:
            The modify labels object to pass to the Gmail API.

        """

        if to_add is None:
            to_add = []

        if to_remove is None:
            to_remove = []

        return {
            "addLabelIds": [
                lbl.id if isinstance(lbl, Label) else lbl for lbl in to_add
            ],
            "removeLabelIds": [
                lbl.id if isinstance(lbl, Label) else lbl for lbl in to_remove
            ],
        }
