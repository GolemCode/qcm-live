"""Formulaires de la banque : sans JavaScript, toutes les règles sont vérifiées côté serveur."""

from __future__ import annotations

from decimal import Decimal

from django import forms
from django.db import transaction

from bank.models import CHOICE_MAX_LENGTH, NONE_OF_THESE, Choice, Question, Quiz, QuizItem
from bank.scoring import (
    LETTERS,
    MAX_CHOICES,
    ScoringError,
    format_scoring,
    parse_points,
    parse_scoring,
    plain,
)
from config.forms import PlainForm, TeacherForm, table_field

MIN_CHOICES = 2
SLOTS = LETTERS[:MAX_CHOICES]
KEEP_ORDER = "Ne pas mélanger les propositions"


class QuestionForm(TeacherForm):
    """Énoncé, type, barème, options, et 8 emplacements de proposition (les vides sont ignorés)."""

    class Meta:
        model = Question
        fields = ["text", "kind", "scoring", "none_of_these", "ordered"]
        labels = {"text": "Énoncé", "scoring": "Barème", "ordered": KEEP_ORDER}
        help_texts = {
            "scoring": "Directives d'Auto Multiple Choice séparées par des virgules, par exemple "
            "b=2,m=-0.5 ou haut=2. Vide : b=1, m=0, v=0.",
            "none_of_these": "Question multiple : ajoutée en dernier, juste si aucune autre "
            "ne l'est.",
        }
        widgets = {"text": forms.Textarea(attrs={"rows": 3}), "kind": forms.RadioSelect}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        existing = list(self.instance.choices.all()) if self.instance.pk else []
        for index, letter in enumerate(SLOTS):
            choice = existing[index] if index < len(existing) else None
            self.fields[f"choice_{letter}"] = table_field(
                forms.CharField(
                    label=f"Proposition {letter}",
                    max_length=CHOICE_MAX_LENGTH,
                    required=False,
                    initial=choice.text if choice else "",
                )
            )
            self.fields[f"correct_{letter}"] = table_field(
                forms.BooleanField(
                    label=f"Proposition {letter} juste",
                    required=False,
                    initial=choice.correct if choice else False,
                )
            )
            points = choice.points if choice else None
            self.fields[f"points_{letter}"] = table_field(
                forms.CharField(
                    label=f"Points de la proposition {letter}",
                    required=False,
                    initial="" if points is None else str(plain(points)),
                )
            )

    def choice_rows(self):
        """(lettre, champ texte, case « juste », points) pour le gabarit."""
        return [(L, self[f"choice_{L}"], self[f"correct_{L}"], self[f"points_{L}"]) for L in SLOTS]

    def clean_scoring(self) -> str:
        try:
            return format_scoring(parse_scoring(self.cleaned_data["scoring"]))
        except ScoringError as error:
            raise forms.ValidationError(f"{error}.") from None

    def clean(self):
        super().clean()
        data = self.cleaned_data
        multiple = data.get("kind") == Question.Kind.MULTIPLE
        choices: list[tuple[str, bool, Decimal | None]] = []
        for letter in SLOTS:
            text = data.get(f"choice_{letter}") or ""  # CharField retire déjà les espaces
            correct = bool(data.get(f"correct_{letter}"))
            points = self._points(letter, text, multiple)
            if text:
                choices.append((text, correct, points))
            elif correct:
                raise forms.ValidationError(
                    f"La proposition {letter} est marquée juste mais elle est vide."
                )
        if len(choices) < MIN_CHOICES:
            raise forms.ValidationError(f"Il faut au moins {MIN_CHOICES} propositions.")
        n_correct = sum(correct for _, correct, _ in choices)
        none_of_these = bool(data.get("none_of_these"))
        if not multiple and none_of_these:
            raise forms.ValidationError(
                f"« {NONE_OF_THESE} » ne s'ajoute qu'à une question multiple."
            )
        if not multiple and n_correct != 1:
            raise forms.ValidationError(
                "Une question à choix simple a exactement une bonne réponse."
            )
        if multiple and n_correct == 0 and not none_of_these:
            raise forms.ValidationError(
                "Une question à choix multiple a au moins une bonne réponse."
            )
        data["choices"] = choices
        return data

    def _points(self, letter: str, text: str, multiple: bool) -> Decimal | None:
        raw = (self.cleaned_data.get(f"points_{letter}") or "").strip()
        if not raw:
            return None
        if multiple:
            raise forms.ValidationError(
                "Les points d'une proposition ne valent que pour une question simple."
            )
        if not text:
            raise forms.ValidationError(f"La proposition {letter} a des points mais elle est vide.")
        try:
            return parse_points(raw)
        except ScoringError as error:
            raise forms.ValidationError(f"Points de la proposition {letter} : {error}.") from None

    @transaction.atomic
    def save(self, commit: bool = True) -> Question:
        question = super().save(commit=commit)
        if not commit:
            return question
        question.choices.all().delete()
        Choice.objects.bulk_create(
            Choice(question=question, text=text, correct=correct, points=points, position=position)
            for position, (text, correct, points) in enumerate(self.cleaned_data["choices"])
        )
        return question


class QuizForm(TeacherForm):
    """Titre et un champ « ordre » par question de la banque (vide = non incluse)."""

    class Meta:
        model = Quiz
        fields = ["title"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        positions = {}
        if self.instance.pk:
            positions = dict(
                QuizItem.objects.filter(quiz=self.instance).values_list("question_id", "position")
            )
        self.bank = list(Question.objects.all())
        for question in self.bank:
            self.fields[self.order_field(question)] = table_field(
                forms.IntegerField(
                    label=f"Ordre de la question : {question.text}",
                    min_value=1,
                    required=False,
                    initial=positions.get(question.pk),
                )
            )

    @staticmethod
    def order_field(question: Question) -> str:
        return f"order_{question.pk}"

    def question_rows(self):
        """(question, champ ordre) pour le gabarit."""
        return [(q, self[self.order_field(q)]) for q in self.bank]

    def clean(self):
        super().clean()
        data = self.cleaned_data
        if any(self.order_field(q) in self.errors for q in self.bank):
            return data  # un numéro d'ordre invalide : son erreur suffit, pas de contrôle croisé
        chosen = [
            (data[self.order_field(q)], q)
            for q in self.bank
            if data.get(self.order_field(q)) is not None
        ]
        if not chosen:
            raise forms.ValidationError(
                "Choisissez au moins une question en lui donnant un numéro d'ordre (1, 2, 3…)."
            )
        ranks = [rank for rank, _ in chosen]
        if len(set(ranks)) != len(ranks):
            raise forms.ValidationError(
                "Deux questions ont le même rang dans l'ordre : chaque numéro est unique."
            )
        data["ordered_questions"] = [q for _, q in sorted(chosen, key=lambda item: item[0])]
        return data

    @transaction.atomic
    def save(self, commit: bool = True) -> Quiz:
        quiz = super().save(commit=commit)
        if not commit:
            return quiz
        QuizItem.objects.filter(quiz=quiz).delete()
        QuizItem.objects.bulk_create(
            QuizItem(quiz=quiz, question=question, position=position)
            for position, question in enumerate(self.cleaned_data["ordered_questions"], start=1)
        )
        return quiz


class AmcUploadForm(PlainForm):
    """Envoi d'un fichier AMC-TXT à l'analyse (IMP-01) ; rien n'est encore créé."""

    file = forms.FileField(label="Fichier AMC-TXT")
