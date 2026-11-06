// Outils communs du tableau et du téléphone : interrogation périodique d'un état JSON et
// compte à rebours. Script externe (CSP stricte), sans dépendance.
window.qcm = {
  // Appelle onState(état) toutes les `period` ms ; s'arrête si onState renvoie false.
  // Une erreur réseau est ignorée : on réessaie au tour suivant.
  poll(url, onState, period = 1000) {
    async function tick() {
      let again = true;
      try {
        const response = await fetch(url, { cache: "no-store" });
        if (response.ok) again = onState(await response.json()) !== false;
      } catch {
        // réseau momentanément indisponible
      }
      if (again) setTimeout(tick, period);
    }
    setTimeout(tick, period);
  },

  // Affiche « N s » dans `element` jusqu'à l'échéance ; un nouvel appel la recale.
  countdown(element, remainingMs) {
    const deadline = Date.now() + remainingMs;
    clearInterval(element.qcmTimer);
    const render = () => {
      const seconds = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      element.textContent = `${seconds} s`;
    };
    render();
    element.qcmTimer = setInterval(render, 250);
  },
};
