"""Lancement d'une session (enseignant) ; code puis nom dans la liste du groupe (étudiant)."""

from __future__ import annotations

from typing import cast

from django import forms
from django.db import IntegrityError, transaction
from django.db.models import Count

from bank.models import NONE_OF_THESE, Quiz
from config.forms import PlainForm
from live.models import CODE_LENGTH, Session, random_code
from live.results import none_index
from live.snapshot import FrozenQuestion, freeze_group, freeze_quiz
from roster.models import StudentGroup

MAX_SHOWN = 6  # SES-01 : de 1 à 6 questions affichées en même temps
DEFAULT_SHOWN = 4  # SES-06
MIN_SECONDS, MAX_SECONDS = 5, 600
CODE_ATTEMPTS = 20  # un million de codes : une collision est rare, vingt d'affilée impossible
INVALID_ANSWER = "Réponse invalide."


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
        label="Questions affichées en même temps",
        min_value=1,
        max_value=MAX_SHOWN,
        initial=DEFAULT_SHOWN,
    )
    seconds = forms.IntegerField(
        label="Temps par question (secondes)",
        min_value=MIN_SECONDS,
        max_value=MAX_SECONDS,
        initial=30,
    )

    def clean(self):
        """Fige le QCM et le groupe tels qu'ils sont, en une lecture cohérente (SES-03)."""
        super().clean()
        quiz, group = self.cleaned_data.get("quiz"), self.cleaned_data.get("group")
        if quiz is not None and group is not None:
            with transaction.atomic():
                self.frozen = {
                    "quiz_title": quiz.title,
                    "group_name": group.name,
                    "content": freeze_quiz(quiz),
                    "roster": freeze_group(group),
                }
            if not self.frozen["content"]["questions"]:
                raise forms.ValidationError("Ce QCM ne contient plus aucune question.")
        return self.cleaned_data

    def save(self) -> Session:
        fields = {
            **self.frozen,
            "n_questions": len(self.frozen["content"]["questions"]),
            "shown": self.cleaned_data["shown"],
            "seconds": self.cleaned_data["seconds"],
        }
        for _ in range(CODE_ATTEMPTS):
            try:
                with transaction.atomic():
                    return Session.objects.create(code=random_code(), **fields)
            except IntegrityError:
                continue  # code déjà attribué : on en tire un autre
        raise RuntimeError("Aucun code de session libre trouvé.")


class DigitsField(forms.CharField):
    """Suite de chiffres tapée sur le pavé numérique du téléphone ; les espaces sont ignorés."""

    def __init__(self, *, label: str, max_length: int) -> None:
        super().__init__(
            label=label,
            max_length=max_length,
            widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
        )

    def widget_attrs(self, widget):
        # Pas d'attribut maxlength : il couperait la saisie d'un code tapé avec des espaces
        # (« 123 456 »). La longueur est vérifiée côté serveur, une fois les espaces retirés.
        attrs = super().widget_attrs(widget)
        attrs.pop("maxlength", None)
        return attrs

    def to_python(self, value) -> str:
        return (super().to_python(value) or "").replace(" ", "")


class JoinForm(PlainForm):
    code = DigitsField(label="Code de session", max_length=CODE_LENGTH)

    def clean_code(self) -> str:
        code = self.cleaned_data["code"]
        if not Session.objects.filter(code=code).exists():
            raise forms.ValidationError("Aucune session ne porte ce code.")
        return code


class AnswerForm(PlainForm):
    """Propositions choisies (indices canoniques) pour la question du créneau en cours."""

    choice = forms.TypedMultipleChoiceField(
        coerce=int,
        required=False,
        error_messages={"invalid_choice": INVALID_ANSWER, "invalid_list": INVALID_ANSWER},
    )

    def __init__(self, *args, question: FrozenQuestion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.multiple = question["multiple"]
        choices = question["choices"]
        self.none = none_index(question)
        field = cast(forms.TypedMultipleChoiceField, self.fields["choice"])
        field.choices = [(i, i) for i in range(len(choices))]

    def clean_choice(self) -> list[int]:
        chosen = sorted(set(self.cleaned_data["choice"]))
        if not self.multiple and len(chosen) > 1:
            raise forms.ValidationError("Une seule proposition pour cette question.")
        if self.none in chosen and len(chosen) > 1:  # ETU-12
            raise forms.ValidationError(
                f"« {NONE_OF_THESE} » ne se combine pas avec une autre proposition."
            )
        return chosen
