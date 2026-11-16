// Téléphone de l'étudiant : suit le direct (poll.js), enregistre chaque choix aussitôt (ETU-04,
// ETU-07), comme l'effacement d'une réponse simple (ETU-09), et tient compte d'un réseau lent
// ou coupé (ETU-10, ETU-11, FIN-02).
//
// Trace des envois : le navigateur garde, pour chaque créneau, la dernière réponse donnée
// (indices canoniques des propositions) et si le serveur l'a confirmée. Une réponse non
// confirmée n'est jamais affichée comme enregistrée ; le téléphone demande au serveur ce qu'il
// a vraiment reçu avant de la déclarer perdue.
(() => {
  const TEXT = {
    sending: "Envoi en cours…",
    saved: "Réponse enregistrée", // comme live.views.SAVED, CLEARED et TOO_LATE
    cleared: "Réponse effacée",
    tooLate: "Temps écoulé : réponse non enregistrée",
    refused: "Réponse refusée : rechargez la page.",
    previousLost: "Votre réponse précédente n'a pas été enregistrée.",
    offline: "Connexion perdue",
    transmitted: "Vos réponses ont été transmises à l'enseignant.",
    notTransmitted: (n) =>
      n === 1
        ? "1 réponse n'a pas pu être transmise : signalez-le à l'enseignant."
        : `${n} réponses n'ont pas pu être transmises : signalez-le à l'enseignant.`,
  };
  const RETRY_MS = 1000; // renvoi d'une réponse, puis d'une question au serveur
  const SEND_TIMEOUT_MS = 8000; // au-delà, l'envoi est tenu pour perdu, et renvoyé

  const body = document.body;
  const qcm = window.qcm;
  if (!body.dataset.trace) return; // téléphone non identifié

  // --- Trace des envois, dans le stockage local (absente en navigation privée refermée) ---
  const traceKey = `qcm-live:${body.dataset.trace}`;
  function readTrace() {
    try {
      return JSON.parse(localStorage.getItem(traceKey)) || {};
    } catch {
      return {};
    }
  }
  function writeTrace(trace) {
    try {
      localStorage.setItem(traceKey, JSON.stringify(trace));
    } catch {
      // stockage refusé : le téléphone n'affirmera rien à la fin (FIN-02)
    }
  }
  function updateTrace(slot, changes) {
    const trace = readTrace();
    trace[slot] = { ...trace[slot], ...changes };
    writeTrace(trace);
  }
  const same = (a, b) => a.length === b.length && a.every((value, i) => value === b[i]);

  // Demande au serveur ce qu'il a enregistré, et confirme les créneaux `slots` dont la
  // dernière réponse donnée y est. Renvoie la trace à jour ; échoue sans réseau.
  async function reconcile(slots) {
    const response = await fetch(body.dataset.answersUrl, {
      cache: "no-store",
      signal: qcm.timeout(5000),
    });
    qcm.contact();
    if (!response.ok) throw new Error(`réponses : ${response.status}`);
    const recorded = (await response.json()).answers;
    const trace = readTrace();
    for (const slot of slots) {
      if (trace[slot] && same(trace[slot].given, recorded[slot] || [])) trace[slot].ok = true;
    }
    writeTrace(trace);
    return trace;
  }

  // Même chose, en réessayant chaque seconde jusqu'à obtenir la réponse du serveur.
  async function reconcileSoon(slots) {
    for (;;) {
      try {
        return await reconcile(slots);
      } catch {
        await new Promise((resolve) => setTimeout(resolve, RETRY_MS));
      }
    }
  }

  const unconfirmed = (trace, keep = () => true) =>
    Object.keys(trace).filter((slot) => !trace[slot].ok && keep(Number(slot)));

  function reveal(element, text) {
    element.textContent = text;
    element.hidden = false;
  }

  // --- Fin de session (FIN-02) -------------------------------------------------------------
  const transmission = document.getElementById("transmission");
  if (transmission) {
    (async () => {
      let trace = readTrace();
      const slots = Object.keys(trace);
      if (slots.length === 0) return; // aucune réponse, ou trace perdue : rien à affirmer
      const pending = unconfirmed(trace);
      if (pending.length) trace = await reconcileSoon(pending);
      const lost = unconfirmed(trace).length;
      reveal(transmission, lost ? TEXT.notTransmitted(lost) : TEXT.transmitted);
    })();
    return;
  }

  // --- Suivi du direct et perte de connexion (ETU-11) ---------------------------------------
  const form = document.getElementById("answer-form");
  const timer = body.querySelector("[role=timer]");
  // Échéance du créneau affiché, sur l'horloge monotone du téléphone, recalée par le serveur.
  let deadline = timer ? performance.now() + Number(timer.dataset.remainingMs) : null;
  qcm.follow(body, (state) => {
    if (state.remaining_ms !== null) deadline = performance.now() + state.remaining_ms;
  });
  qcm.watchConnection(body.querySelector(".offline"), TEXT.offline);
  if (!form) return; // en attente

  const slot = body.dataset.slot;
  const status = document.getElementById("save-status");
  const clear = document.getElementById("clear-answer");
  const inputs = [...form.querySelectorAll("input[name=choice]")];
  const show = (text) => {
    status.textContent = text;
  };
  const chosen = () =>
    inputs
      .filter((input) => input.checked)
      .map((input) => Number(input.value))
      .sort((a, b) => a - b);
  const confirmedText = (given) => (given.length ? TEXT.saved : TEXT.cleared);

  // --- Envoi de la réponse (ETU-10) --------------------------------------------------------
  // Un seul envoi à la fois, avec l'état du formulaire au départ. S'il a changé entre-temps,
  // le nouvel état part aussitôt après : la dernière réponse arrive toujours en dernier. Sans
  // réseau, ou si le serveur est momentanément indisponible, l'envoi recommence chaque
  // seconde tant que le créneau dure.
  let sending = false;
  let retry = null;
  async function send() {
    if (sending) return;
    clearTimeout(retry);
    sending = true;
    const given = chosen();
    const data = new FormData(form);
    let outcome = "retry";
    let message = "";
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: data,
        signal: qcm.timeout(SEND_TIMEOUT_MS),
      });
      qcm.contact();
      const json = (response.headers.get("Content-Type") || "").includes("application/json");
      if (response.status < 500) {
        outcome = response.ok && json ? "saved" : "refused";
        message = json ? (await response.json()).message : TEXT.refused;
      }
    } catch {
      // réseau indisponible, ou réponse jamais arrivée
    }
    sending = false;
    if (!same(given, chosen())) {
      send(); // l'étudiant a changé d'avis pendant l'envoi
      return;
    }
    if (outcome === "saved") {
      updateTrace(slot, { ok: true });
      show(message);
    } else if (outcome === "refused") {
      show(message); // hors délai (ETU-07), ou refus : rien à renvoyer
    } else if (performance.now() < deadline) {
      retry = setTimeout(send, RETRY_MS);
    }
  }

  function changed() {
    if (clear) clear.disabled = !inputs.some((input) => input.checked);
    updateTrace(slot, { given: chosen(), ok: false });
    show(TEXT.sending);
    send();
  }
  form.addEventListener("change", changed);
  if (clear) {
    clear.addEventListener("click", () => {
      for (const input of inputs) input.checked = false;
      changed();
    });
  }

  // À l'échéance, une réponse non confirmée est signalée comme non enregistrée, sauf si le
  // serveur dit l'avoir reçue à temps (sa confirmation s'était perdue).
  const watch = setInterval(async () => {
    if (performance.now() < deadline) return;
    clearInterval(watch);
    clearTimeout(retry);
    const entry = readTrace()[slot];
    if (!entry || entry.ok) return;
    try {
      if ((await reconcile([slot]))[slot].ok) {
        show(confirmedText(entry.given));
        return;
      }
    } catch {
      // pas de réseau : le téléphone ne peut pas savoir
    }
    show(TEXT.tooLate);
  }, 250);

  // --- Au chargement : rechargement en cours d'envoi, créneaux précédents --------------------
  const trace = readTrace();
  const entry = trace[slot];
  if (entry && !entry.ok) {
    if (same(entry.given, chosen())) {
      updateTrace(slot, { ok: true }); // le serveur l'a reçue : la page l'affiche
    } else {
      // Envoi encore en attente : le dernier choix est réaffiché et renvoyé (décision I11).
      for (const input of inputs) input.checked = entry.given.includes(Number(input.value));
      changed();
    }
  }
  // Réponse d'un créneau précédent jamais confirmée : on demande au serveur, puis on le dit
  // sur cet écran, le premier qui suit (et sur lui seulement, s'il est rechargé).
  const earlier = unconfirmed(trace, (other) => other < Number(slot));
  if (earlier.length) {
    reconcileSoon(earlier).then((updated) => {
      const lost = unconfirmed(updated, (other) => other < Number(slot)).filter(
        (other) => updated[other].told === undefined || updated[other].told === slot,
      );
      if (lost.length === 0) return;
      for (const other of lost) updated[other].told = slot;
      writeTrace(updated);
      reveal(document.getElementById("previous-lost"), TEXT.previousLost);
    });
  }
})();
