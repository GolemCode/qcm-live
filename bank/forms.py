"""Formulaires de la banque : sans JavaScript, toutes les règles sont vérifiées côté serveur."""

from __future__ import annotations

from django import forms
from django.db import transaction

from bank.models import CHOICE_MAX_LENGTH, Choice, Question, Quiz, QuizItem
from config.forms import TeacherForm, table_field

LETTERS = "ABCDEFGH"  # 2 à 8 propositions, désignées A…H comme au tableau
MIN_CHOICES = 2


class QuestionForm(TeacherForm):
    """Énoncé, type, et 8 emplacements de proposition (les vides sont ignorés)."""

    class Meta:
        model = Question
        fields = ["text", "kind"]
        labels = {"text": "Énoncé"}
        widgets = {"text": forms.Textarea(attrs={"rows": 3}), "kind": forms.RadioSelect}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        existing = list(self.instance.choices.all()) if self.instance.pk else []
        for index, letter in enumerate(LETTERS):
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

    def choice_rows(self):
        """(lettre, champ texte, case « juste ») pour le gabarit."""
        return [(L, self[f"choice_{L}"], self[f"correct_{L}"]) for L in LETTERS]

    def clean(self):
        super().clean()
        data = self.cleaned_data
        choices: list[tuple[str, bool]] = []
        for letter in LETTERS:
            text = data.get(f"choice_{letter}") or ""  # CharField retire déjà les espaces
            correct = bool(data.get(f"correct_{letter}"))
            if text:
                choices.append((text, correct))
            elif correct:
                raise forms.ValidationError(
                    f"La proposition {letter} est marquée juste mais elle est vide."
                )
        if len(choices) < MIN_CHOICES:
            raise forms.ValidationError(f"Il faut au moins {MIN_CHOICES} propositions.")
        n_correct = sum(correct for _, correct in choices)
        if data.get("kind") == Question.Kind.SIMPLE and n_correct != 1:
            raise forms.ValidationError(
                "Une question à choix simple a exactement une bonne réponse."
            )
        if data.get("kind") == Question.Kind.MULTIPLE and n_correct == 0:
            raise forms.ValidationError(
                "Une question à choix multiple a au moins une bonne réponse."
            )
        data["choices"] = choices
        return data

    @transaction.atomic
    def save(self, commit: bool = True) -> Question:
        question = super().save(commit=commit)
        if not commit:
            return question
        question.choices.all().delete()
        Choice.objects.bulk_create(
            Choice(question=question, text=text, correct=correct, position=position)
            for position, (text, correct) in enumerate(self.cleaned_data["choices"])
        )
        return question


SIMPLE_SCALE_FIELDS = ["simple_b", "simple_m", "simple_v"]
MULTIPLE_SCALE_FIELDS = ["multiple_b", "multiple_m", "multiple_v", "multiple_p"]


class QuizForm(TeacherForm):
    """Titre, barème, et un champ « ordre » par question de la banque (vide = non incluse)."""

    class Meta:
        model = Quiz
        fields = ["title", *SIMPLE_SCALE_FIELDS, *MULTIPLE_SCALE_FIELDS]
        # Directives AMC en minuscules, comme dans AMC (« b — … »).
        labels = {
            "simple_b": "b — réponse juste",
            "simple_m": "m — réponse fausse",
            "simple_v": "v — pas de réponse",
            "multiple_b": "b — case bien traitée",
            "multiple_m": "m — case mal traitée",
            "multiple_v": "v — aucune case cochée",
            "multiple_p": "p — plancher (facultatif)",
        }

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

    def scale_fieldsets(self):
        return [
            ("Questions simples", [self[name] for name in SIMPLE_SCALE_FIELDS]),
            ("Questions multiples", [self[name] for name in MULTIPLE_SCALE_FIELDS]),
        ]

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
