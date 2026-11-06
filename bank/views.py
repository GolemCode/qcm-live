"""Pages enseignant : banque de questions et QCM (création, modification, suppression)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from bank.forms import QuestionForm, QuizForm
from bank.models import Question, Quiz


@login_required
def question_list(request: HttpRequest) -> HttpResponse:
    questions = Question.objects.prefetch_related("choices", "quizzes")
    return render(request, "bank/question_list.html", {"questions": questions})


@login_required
def question_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    question = get_object_or_404(Question, pk=pk) if pk is not None else Question()
    form = QuestionForm(request.POST or None, instance=question)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Question enregistrée.")
        return redirect("question-list")
    return render(request, "bank/question_form.html", {"form": form, "question": question})


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
