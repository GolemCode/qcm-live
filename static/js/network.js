// Page « Réseau et téléphones » (CLA-04) : attend qu'un téléphone ouvre l'adresse d'essai,
// puis l'annonce. Script externe (CSP stricte), texte inséré avec textContent.
(() => {
  const status = document.querySelector("[data-trial-url]");
  if (!status) return;
  window.qcm.poll(status.dataset.trialUrl, (state) => {
    if (!state.connected) return true;
    status.textContent = "Téléphone connecté";
    status.classList.add("ok");
    return false;
  });
})();
