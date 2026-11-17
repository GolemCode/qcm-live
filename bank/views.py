"""Pages enseignant : banque de questions et QCM (création, modification, suppression)."""

import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import pluralize

from bank.amc_txt import MAX_BYTES, AmcSyntaxError
from bank.forms import AmcUploadForm, QuestionForm, QuizCopyForm, QuizForm, VersionScopeForm
from bank.importer import Preview, import_quiz, preview, same_file, sha256
from bank.models import NONE_OF_THESE, PendingImport, Question, Quiz


@login_required
def question_list(request: HttpRequest) -> HttpResponse:
    questions = Question.current().prefetch_related("choices", "quizzes", "previous")
    return render(
        request,
        "bank/question_list.html",
        {"questions": questions, "none_of_these": NONE_OF_THESE},
    )


def _from_quiz(request: HttpRequest, question: Question) -> Quiz | None:
    """Le QCM depuis lequel la question est modifiée (`?qcm=`), s'il la contient (VER-02)."""
    pk = request.GET.get("qcm", "")
    if not pk.isdigit() or question.pk is None:
        return None
    return Quiz.objects.filter(pk=pk, questions=question).first()


@login_required
def question_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    question = get_object_or_404(Question, pk=pk) if pk is not None else Question()
    quiz = _from_quiz(request, question)
    # Déjà servie dans une session lancée : la modifier crée une nouvelle version (VER-01).
    used = question.pk is not None and question.sessions.exists()
    before = question.content() if used else None
    form = QuestionForm(request.POST or None, instance=question)
    scope = VersionScopeForm(request.POST or None, quiz=quiz) if used and quiz else None
    valid = form.is_valid() and (scope is None or scope.is_valid())
    if request.method == "POST" and valid:
        if not used:
            form.save()
            messages.success(request, "Question enregistrée.")
        elif form.content() == before:
            messages.info(request, "Aucun changement : rien n'est enregistré.")
        else:
            only = quiz if scope and scope.cleaned_data["scope"] == scope.ONLY else None
            form.save_version(only)
            messages.success(request, "Nouvelle version enregistrée.")
        if quiz is not None:
            return redirect("quiz-detail", pk=quiz.pk)
        return redirect("question-list")
    context = {"form": form, "question": question, "quiz": quiz, "used": used, "scope": scope}
    if used:
        context["touched"] = Quiz.objects.filter(questions=question)
    return render(request, "bank/question_form.html", context)


@login_required
def question_delete(request: HttpRequest, pk: int) -> HttpResponse:
    question = get_object_or_404(Question, pk=pk)
    if request.method == "POST":
        question.delete()
        messages.success(request, "Question supprimée.")
        return redirect("question-list")
    return render(request, "bank/question_confirm_delete.html", {"question": question})


@login_required
def quiz_list(request: HttpRequest) -> HttpResponse:
    quizzes = Quiz.objects.annotate(n_questions=Count("questions"))
    return render(request, "bank/quiz_list.html", {"quizzes": quizzes})


@login_required
def quiz_detail(request: HttpRequest, pk: int) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=pk)
    return render(
        request, "bank/quiz_detail.html", {"quiz": quiz, "questions": quiz.ordered_questions()}
    )


@login_required
def quiz_remove(request: HttpRequest, pk: int, question: int) -> HttpResponse:
    """Retire une question de ce seul QCM ; elle reste dans la banque (CMP-05)."""
    quiz = get_object_or_404(Quiz, pk=pk)
    if request.method == "POST":
        kept = quiz.ordered_questions().exclude(pk=question).values_list("pk", flat=True)
        quiz.set_questions(list(kept))
        messages.success(request, "Question retirée du QCM.")
    return redirect("quiz-detail", pk=quiz.pk)


@login_required
def quiz_copy(request: HttpRequest, pk: int) -> HttpResponse:
    """Nouveau QCM qui reprend celui-ci en entier (CMP-01)."""
    source = get_object_or_404(Quiz, pk=pk)
    form = QuizCopyForm(request.POST or None, source=source)
    if request.method == "POST" and form.is_valid():
        quiz = form.save()
        messages.success(request, "QCM créé.")
        return redirect("quiz-detail", pk=quiz.pk)
    return render(request, "bank/quiz_copy.html", {"form": form, "source": source})


@login_required
def quiz_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=pk) if pk is not None else Quiz()
    form = QuizForm(request.POST or None, instance=quiz)
    if request.method == "POST" and form.is_valid():
        quiz = form.save()
        messages.success(request, "QCM enregistré.")
        return redirect("quiz-detail", pk=quiz.pk)
    return render(request, "bank/quiz_form.html", {"form": form, "quiz": quiz})


@login_required
def quiz_delete(request: HttpRequest, pk: int) -> HttpResponse:
    quiz = get_object_or_404(Quiz, pk=pk)
    if request.method == "POST":
        quiz.delete()
        messages.success(request, "QCM supprimé.")
        return redirect("quiz-list")
    return render(request, "bank/quiz_confirm_delete.html", {"quiz": quiz})


# --- Import AMC-TXT (IMP-01) : envoi, récapitulatif, confirmation ------------------------------

EXPIRED = "Cet import n'est plus disponible : envoyez de nouveau le fichier."


def _analyse(data: bytes, name: str) -> Preview | list[str]:
    """Le récapitulatif, ou les raisons du refus."""
    try:
        return preview(data, name)
    except AmcSyntaxError as error:
        return error.messages


@login_required
def quiz_import(request: HttpRequest) -> HttpResponse:
    form = AmcUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data["file"]
        data, name = upload.read(MAX_BYTES + 1), upload.name or ""
        found = _analyse(data, name)
        if isinstance(found, list):
            form.add_error(None, found)
        else:
            token = secrets.token_urlsafe(16)
            PendingImport.objects.update_or_create(
                user=request.user, defaults={"token": token, "name": name, "data": data}
            )
            return redirect("quiz-import-recap", token=token)
    return render(request, "bank/quiz_import.html", {"form": form})


@login_required
def quiz_import_recap(request: HttpRequest, token: str) -> HttpResponse:
    pending = PendingImport.objects.filter(user=request.user, token=token).first()
    if pending is None:
        messages.error(request, EXPIRED)
        return redirect("quiz-import")
    data, name = bytes(pending.data), pending.name
    if request.method == "POST":
        # Seule la requête qui efface l'envoi le traite : un double clic retombe sur EXPIRED.
        deleted, _ = PendingImport.objects.filter(pk=pending.pk, token=token).delete()
        if not deleted:
            messages.error(request, EXPIRED)
            return redirect("quiz-import")
        if request.POST.get("action") != "import":
            messages.success(request, "Import annulé.")
            return redirect("quiz-list")
        target = same_file(sha256(data))
        before = target.questions.count() if target else 0
        try:
            quiz = import_quiz(data, name)
        except ValueError as error:  # refus de l'analyse
            messages.error(request, str(error))
            return redirect("quiz-import")
        n = quiz.questions.count()
        if target is None:
            messages.success(request, f"QCM importé : {n} question{pluralize(n)}.")
        else:  # réimport (IMP-10)
            added = n - before
            ajoutee = f"{added} question{pluralize(added)} ajoutée{pluralize(added)}"
            messages.success(request, f"QCM complété : {ajoutee if added else 'rien à ajouter'}.")
        return redirect("quiz-detail", pk=quiz.pk)
    found = _analyse(data, name)
    if isinstance(found, list):  # analysé sans erreur à l'envoi : ne devrait pas arriver
        pending.delete()
        for message in found:
            messages.error(request, message)
        return redirect("quiz-import")
    return render(request, "bank/quiz_import_recap.html", {"found": found, "name": name})
