"""Formulaires de la banque : sans JavaScript, toutes les règles sont vérifiées côté serveur."""

from __future__ import annotations

from decimal import Decimal

from django import forms
from django.db import transaction

from bank.composition import arrange
from bank.models import CHOICE_MAX_LENGTH, NONE_OF_THESE, Choice, Question, Quiz, QuizItem
from bank.scoring import (
    LETTERS,
    MAX_CHOICES,
    SCORING_MAX_LENGTH,
    ScoringError,
    format_points,
    format_scoring,
    parse_points,
    parse_scoring,
)
from config.forms import PlainForm, TeacherForm, table_field

MIN_CHOICES = 2
SLOTS = LETTERS[:MAX_CHOICES]
KEEP_ORDER = "Ne pas mélanger les propositions"
INCLUDE = "Inclure la question : "  # libellé de la case de composition (CMP-04)


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
                    initial=format_points(points),
                )
            )

    def choice_rows(self):
        """(lettre, champ texte, case « juste », points) pour le gabarit."""
        return [(L, self[f"choice_{L}"], self[f"correct_{L}"], self[f"points_{L}"]) for L in SLOTS]

    def clean_scoring(self) -> str:
        try:
            scoring = format_scoring(parse_scoring(self.cleaned_data["scoring"]))
        except ScoringError as error:
            raise forms.ValidationError(f"{error}.") from None
        if len(scoring) > SCORING_MAX_LENGTH:  # `.5` devient `0.5`
            raise forms.ValidationError(
                f"Au plus {SCORING_MAX_LENGTH} caractères une fois réécrit ({len(scoring)} ici)."
            )
        return scoring

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

    def content(self) -> tuple[object, ...]:
        """Contenu saisi, comparable à `Question.content` (VER-01)."""
        data = self.cleaned_data
        text = data["text"].replace("\r\n", "\n")  # le navigateur renvoie des CRLF
        fields = (data["kind"], data["scoring"], data["none_of_these"], data["ordered"])
        return (text, *fields, tuple(data["choices"]))

    @transaction.atomic
    def save_version(self, only: Quiz | None = None) -> Question:
        """Enregistre la saisie comme nouvelle version de la question, qui reste inchangée
        (VER-01), et la met à sa place dans ses QCM, ou dans le seul `only` (VER-02)."""
        old = Question.objects.get(pk=self.instance.pk)
        new = self.instance  # porte déjà la saisie, et l'étiquette AMC de l'ancienne
        new.pk, new.previous = None, old
        new._state.adding = True
        self.save()
        items = QuizItem.objects.filter(question=old)
        if only is not None:
            items = items.filter(quiz=only)
        items.update(question=new)
        # L'origine (IMP-10) suit la version qui occupe sa place dans le QCM de son fichier.
        kept = Quiz.objects.filter(quizitem__question=old).values("source_sha256")
        old.origins.exclude(sha256__in=kept).update(question=new)
        return new

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


class VersionScopeForm(PlainForm):
    """Portée d'une nouvelle version modifiée depuis la fiche d'un QCM (VER-02)."""

    ALL, ONLY = "all", "only"

    def __init__(self, *args, quiz: Quiz, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["scope"] = forms.ChoiceField(
            label="Remplacer la question",
            choices=[(self.ALL, "Dans tous ces QCM"), (self.ONLY, f"Seulement dans « {quiz} »")],
            initial=self.ALL,
            widget=forms.RadioSelect,
        )


class QuizForm(TeacherForm):
    """Titre et une case par question de la banque (CMP-04) ; l'ordre suit `arrange`."""

    class Meta:
        model = Quiz
        fields = ["title"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.current = (
            list(
                self.instance.questions.values_list("pk", flat=True).order_by("quizitem__position")
            )
            if self.instance.pk
            else []
        )
        included = set(self.current)
        self.bank = list(Question.current())
        for question in self.bank:
            self.fields[self.include_field(question)] = table_field(
                forms.BooleanField(
                    label=f"{INCLUDE}{question.text}",
                    required=False,
                    initial=question.pk in included,
                )
            )

    @staticmethod
    def include_field(question: Question) -> str:
        return f"include_{question.pk}"

    def question_rows(self):
        """(question, case à cocher) pour le gabarit."""
        return [(q, self[self.include_field(q)]) for q in self.bank]

    def clean(self):
        super().clean()
        chosen = [q.pk for q in self.bank if self.cleaned_data.get(self.include_field(q))]
        if not chosen:
            raise forms.ValidationError("Cochez au moins une question.")
        self.cleaned_data["chosen"] = chosen
        return self.cleaned_data

    @transaction.atomic
    def save(self, commit: bool = True) -> Quiz:
        quiz = super().save(commit=commit)
        if commit:
            chosen = self.cleaned_data["chosen"]
            quiz.set_questions(arrange(self.current, chosen, quiz.file_ranks()))
        return quiz


class QuizCopyForm(TeacherForm):
    """Nouveau QCM qui reprend un ancien en entier (CMP-01) : seul le titre se saisit."""

    class Meta:
        model = Quiz
        fields = ["title"]

    def __init__(self, *args, source: Quiz, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.source = source

    @transaction.atomic
    def save(self, commit: bool = True) -> Quiz:
        quiz = super().save(commit=commit)
        if commit:
            quiz.set_questions(self.source.ordered_questions().values_list("pk", flat=True))
        return quiz


class AmcUploadForm(PlainForm):
    """Envoi d'un fichier AMC-TXT à l'analyse (IMP-01) ; rien n'est encore créé."""

    file = forms.FileField(label="Fichier AMC-TXT")
