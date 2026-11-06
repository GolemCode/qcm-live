"""Formulaires de la banque : sans JavaScript, toutes les règles sont vérifiées côté serveur."""

from __future__ import annotations

from django import forms
from django.db import transaction

from bank.models import SCALE_LABELS, Choice, Question, Quiz, QuizItem

LETTERS = "ABCDEFGH"  # 2 à 8 propositions, désignées A…H comme au tableau
MIN_CHOICES = 2


class QuestionForm(forms.Form):
    text = forms.CharField(
        label="Énoncé", max_length=1000, widget=forms.Textarea(attrs={"rows": 3})
    )
    kind = forms.ChoiceField(
        label="Type",
        choices=[
            (Question.Kind.SIMPLE, "Choix simple (une seule bonne réponse)"),
            (Question.Kind.MULTIPLE, "Choix multiple (une ou plusieurs bonnes réponses)"),
        ],
        widget=forms.RadioSelect,
        initial=Question.Kind.SIMPLE,
    )

    def __init__(self, *args, instance: Question | None = None, **kwargs) -> None:
        self.instance = instance
        if instance is not None:
            initial = {"text": instance.text, "kind": instance.kind}
            for letter, choice in zip(LETTERS, instance.choices.all(), strict=False):
                initial[f"choice_{letter}"] = choice.text
                initial[f"correct_{letter}"] = choice.correct
            kwargs.setdefault("initial", initial)
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        for letter in LETTERS:
            # Pas de <label> visible dans le tableau : aria-label donne le nom accessible.
            text_label, correct_label = f"Proposition {letter}", f"Proposition {letter} juste"
            self.fields[f"choice_{letter}"] = forms.CharField(
                label=text_label,
                max_length=200,
                required=False,
                widget=forms.TextInput(attrs={"aria-label": text_label}),
            )
            self.fields[f"correct_{letter}"] = forms.BooleanField(
                label=correct_label,
                required=False,
                widget=forms.CheckboxInput(attrs={"aria-label": correct_label}),
            )

    def choice_rows(self):
        """(lettre, champ texte, case « juste ») pour le gabarit."""
        return [(L, self[f"choice_{L}"], self[f"correct_{L}"]) for L in LETTERS]

    def clean(self):
        super().clean()
        data = self.cleaned_data
        choices: list[tuple[str, bool]] = []
        for letter in LETTERS:
            text = (data.get(f"choice_{letter}") or "").strip()
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
    def save(self) -> Question:
        question = self.instance or Question()
        question.text = self.cleaned_data["text"]
        question.kind = self.cleaned_data["kind"]
        question.save()
        question.choices.all().delete()
        Choice.objects.bulk_create(
            Choice(question=question, text=text, correct=correct, position=position)
            for position, (text, correct) in enumerate(self.cleaned_data["choices"])
        )
        return question


SIMPLE_SCALE_FIELDS = ["simple_b", "simple_m", "simple_v"]
MULTIPLE_SCALE_FIELDS = ["multiple_b", "multiple_m", "multiple_v", "multiple_p"]


class QuizForm(forms.ModelForm):
    """Titre, barème, et un champ « ordre » par question de la banque (vide = non incluse)."""

    class Meta:
        model = Quiz
        fields = ["title", *SIMPLE_SCALE_FIELDS, *MULTIPLE_SCALE_FIELDS]
        # Libellés donnés tels quels : les directives AMC restent en minuscules (« b — … »).
        labels = {"title": "Titre", **SCALE_LABELS}

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        positions = {}
        if self.instance.pk:
            positions = dict(
                QuizItem.objects.filter(quiz=self.instance).values_list("question_id", "position")
            )
        self.bank = list(Question.objects.all())
        for question in self.bank:
            label = f"Ordre de la question : {question.text}"
            self.fields[self.order_field(question)] = forms.IntegerField(
                label=label,
                min_value=1,
                required=False,
                initial=positions.get(question.pk),
                widget=forms.NumberInput(attrs={"aria-label": label}),
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
        quiz = super().save()
        QuizItem.objects.filter(quiz=quiz).delete()
        QuizItem.objects.bulk_create(
            QuizItem(quiz=quiz, question=question, position=position)
            for position, question in enumerate(self.cleaned_data["ordered_questions"], start=1)
        )
        return quiz
