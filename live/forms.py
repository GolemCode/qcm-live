"""Lancement d'une session (enseignant) ; code puis numéro (étudiant)."""

from __future__ import annotations

from django import forms
from django.db import IntegrityError, transaction
from django.db.models import Count

from bank.models import Quiz
from config.forms import PlainForm
from live.models import MAX_SECONDS, MAX_SHOWN, MIN_SECONDS, Participant, Session, random_code
from live.snapshot import freeze_group, freeze_quiz
from roster.models import StudentGroup

NUMERIC_KEYPAD = {"inputmode": "numeric", "autocomplete": "off"}


class LaunchSessionForm(PlainForm):
    quiz = forms.ModelChoiceField(
        label="QCM",
        queryset=Quiz.objects.alias(n_questions=Count("questions")).filter(n_questions__gt=0),
        empty_label=None,
    )
    group = forms.ModelChoiceField(
        label="Groupe", queryset=StudentGroup.objects.all(), empty_label=None
    )
    shown = forms.IntegerField(
        label="Questions affichées en même temps", min_value=1, max_value=MAX_SHOWN, initial=1
    )
    seconds = forms.IntegerField(
        label="Temps par question (secondes)",
        min_value=MIN_SECONDS,
        max_value=MAX_SECONDS,
        initial=30,
    )

    def save(self) -> Session:
        quiz, group = self.cleaned_data["quiz"], self.cleaned_data["group"]
        fields = {
            "quiz_title": quiz.title,
            "group_name": group.name,
            "content": freeze_quiz(quiz),
            "roster": freeze_group(group),
            "shown": self.cleaned_data["shown"],
            "seconds": self.cleaned_data["seconds"],
        }
        while True:  # un million de codes : une collision est rare, on retire alors un code
            try:
                with transaction.atomic():
                    return Session.objects.create(code=random_code(), **fields)
            except IntegrityError:
                continue


class JoinForm(PlainForm):
    code = forms.CharField(
        label="Code de session", max_length=20, widget=forms.TextInput(attrs=NUMERIC_KEYPAD)
    )

    def clean_code(self) -> Session:
        code = self.cleaned_data["code"].replace(" ", "")
        session = Session.objects.filter(code=code).first()
        if session is None:
            raise forms.ValidationError("Aucune session ne porte ce code.")
        return session


ALREADY_TAKEN = "Ce numéro est déjà utilisé dans cette session, depuis un autre appareil."


class IdentifyForm(PlainForm):
    number = forms.CharField(
        label="Numéro d'étudiant", max_length=40, widget=forms.TextInput(attrs=NUMERIC_KEYPAD)
    )

    def __init__(self, *args, session: Session, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.session = session

    def clean_number(self) -> str:
        number = self.cleaned_data["number"].replace(" ", "")
        if self.session.student_name(number) is None:
            raise forms.ValidationError("Ce numéro ne fait pas partie du groupe de cette session.")
        if self.session.participants.filter(number=number).exists():
            raise forms.ValidationError(ALREADY_TAKEN)
        return number

    def save(self) -> Participant | None:
        """Le participant, ou None si le numéro a été pris entre-temps (erreur ajoutée)."""
        number = self.cleaned_data["number"]
        try:
            with transaction.atomic():
                return Participant.objects.create(
                    session=self.session,
                    number=number,
                    name=self.session.student_name(number) or "",
                )
        except IntegrityError:
            self.add_error("number", ALREADY_TAKEN)
            return None
