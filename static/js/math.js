// Formules des énoncés et des propositions (CNT-01) : chaque `span.math[data-tex]` reçoit le rendu
// KaTeX de son code, qu'il contient en texte. Une formule que KaTeX refuse garde ce code, marqué.
// Erreurs levées plutôt que rendues (throwOnError) et \pmb remplacé : KaTeX poserait sinon un
// attribut `style`, que la CSP refuse.
"use strict";
(() => {
  const macros = { "\\pmb": "\\boldsymbol{#1}" };
  for (const element of document.querySelectorAll("[data-tex]")) {
    const tex = element.dataset.tex;
    try {
      katex.render(tex, element, {
        displayMode: element.dataset.display === "true",
        throwOnError: true,
        macros: { ...macros },
      });
    } catch (error) {
      element.textContent = tex;
      element.classList.add("math-error");
      element.title = error.message;
    }
  }
})();
