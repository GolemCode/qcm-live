// Outils communs du tableau et du téléphone : interrogation périodique d'un état JSON,
// compte à rebours, et suivi d'une page « en direct ». Script externe (CSP stricte).
window.qcm = {
  // Appelle onState(état) tout de suite puis toutes les `period` ms ; s'arrête si onState
  // renvoie false. Une erreur réseau est ignorée : on réessaie au tour suivant.
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
    tick();
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

  // Page qui suit le direct : `root` porte data-state-url et data-page (jeton de la page).
  // Dès que l'état annonce un autre jeton, la page se recharge, avec un léger décalage
  // aléatoire pour étaler les requêtes d'une classe entière. Sinon, le compte à rebours
  // se recale et onState reçoit l'état.
  follow(root, onState) {
    const timer = root.querySelector("[role=timer]");
    if (timer) this.countdown(timer, Number(timer.dataset.remainingMs));
    this.poll(root.dataset.stateUrl, (state) => {
      if (state.page !== root.dataset.page) {
        setTimeout(() => window.location.reload(), Math.random() * 300);
        return false;
      }
      if (timer && state.remaining_ms !== null) this.countdown(timer, state.remaining_ms);
      if (onState) onState(state);
      return true;
    });
  },
};
