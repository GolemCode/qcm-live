// Téléphone de l'étudiant : suit le direct (poll.js), enregistre chaque choix aussitôt (ETU-04,
// ETU-07), comme l'effacement d'une réponse simple (ETU-09), et tient compte d'un réseau lent
// ou coupé (ETU-10, ETU-11, FIN-02).
//
// Trace des envois : le navigateur garde, pour chaque créneau, la dernière réponse donnée
// (indices canoniques des propositions) et si le serveur l'a confirmée. Une réponse non
// confirmée n'est jamais affichée comme enregistrée ; le téléphone demande au serveur ce qu'il
// a vraiment reçu avant de la déclarer perdue.
(() => {
  // Les messages que le serveur envoie aussi (enregistrée, effacée, hors délai) viennent de la
  // page, qui les tient de live.views : une seule rédaction.
  const TEXT = {
    sending: "Envoi en cours…",
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
  const REFUSED = "refusé"; // le serveur répond, mais refuse : inutile de réessayer

  const body = document.body;
  const qcm = window.qcm;
  if (!body.dataset.trace) return; // téléphone non identifié

  // --- Trace des envois ----------------------------------------------------------------------
  // Tenue en mémoire pour la page affichée, et recopiée dans le stockage local pour la page
  // suivante. Si le stockage est refusé ou plein, le créneau affiché fonctionne quand même ;
  // seule la page suivante n'en saura rien (FIN-02 : elle n'affirme alors rien).
  const traceKey = `qcm-live:${body.dataset.trace}`;
  let current = {};
  try {
    current = JSON.parse(localStorage.getItem(traceKey)) || {};
  } catch {
    // stockage illisible ou refusé : trace vide
  }
  const readTrace = () => JSON.parse(JSON.stringify(current));
  function writeTrace(trace) {
    current = trace;
    try {
      localStorage.setItem(traceKey, JSON.stringify(trace));
    } catch {
      // stockage refusé ou plein
    }
  }
  function updateTrace(slot, changes) {
    const trace = readTrace();
    trace[slot] = { ...trace[slot], ...changes };
    writeTrace(trace);
  }
  const same = (a, b) => a.length === b.length && a.every((value, i) => value === b[i]);

  // Demande au serveur ce qu'il a enregistré, et confirme les créneaux `slots` dont la
  // dernière réponse donnée y est. Renvoie la trace à jour ; échoue sans réseau, ou avec
  // REFUSED si le serveur refuse (identité perdue, session supprimée).
  async function reconcile(slots) {
    const response = await qcm.request(body.dataset.answersUrl);
    if (!response.ok) throw response.status < 500 ? REFUSED : new Error(`${response.status}`);
    const recorded = (await response.json()).answers;
    const trace = readTrace();
    for (const slot of slots) {
      if (trace[slot] && same(trace[slot].given, recorded[slot] || [])) trace[slot].ok = true;
    }
    writeTrace(trace);
    return trace;
  }

  // Même chose, en réessayant chaque seconde tant que le serveur ne répond pas. Renvoie null
  // s'il refuse : le téléphone ne peut alors rien affirmer.
  async function reconcileSoon(slots) {
    for (;;) {
      try {
        return await reconcile(slots);
      } catch (error) {
        if (error === REFUSED) return null;
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
      if (trace === null) return;
      const lost = unconfirmed(trace).length;
      // Tout effacé et confirmé : l'étudiant n'a donné aucune réponse.
      if (!lost && !Object.values(trace).some((entry) => entry.given.length)) return;
      transmission.classList.toggle("error", lost > 0);
      reveal(transmission, lost ? TEXT.notTransmitted(lost) : TEXT.transmitted);
    })();
    return;
  }

  // --- Suivi du direct et perte de connexion (ETU-11) ---------------------------------------
  const form = document.getElementById("answer-form");
  qcm.follow(body);
  qcm.watchConnection(body.querySelector(".offline"), TEXT.offline);
  if (!form) return; // en attente

  // Échéance du créneau affiché, tenue par le compte à rebours (poll.js) et recalée sur le
  // serveur à chaque interrogation.
  const timer = body.querySelector("[role=timer]");
  const ended = () => performance.now() >= timer.qcmDeadline;
  const slot = form.elements.slot.value;
  const status = document.getElementById("save-status");
  const { saved, cleared, tooLate } = status.dataset;
  const clear = document.getElementById("clear-answer");
  const fieldset = form.querySelector("fieldset");
  const inputs = [...form.querySelectorAll("input[name=choice]")];
  const show = (text) => {
    status.textContent = text;
  };
  // Proposition choisie en noir plein (VIS-04) : une classe, que tout navigateur applique.
  const mark = () => {
    for (const input of inputs) input.closest("label").classList.toggle("chosen", input.checked);
    if (clear) clear.disabled = fieldset.disabled || !inputs.some((input) => input.checked);
  };
  const chosen = () =>
    inputs
      .filter((input) => input.checked)
      .map((input) => Number(input.value))
      .sort((a, b) => a - b);

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
      const response = await qcm.request(
        form.action,
        { method: "POST", body: data },
        SEND_TIMEOUT_MS,
      );
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
    if (outcome === "saved") updateTrace(slot, { ok: true });
    if (outcome !== "retry") show(message); // refus : hors délai (ETU-07) ; rien à renvoyer
    else if (!ended()) retry = setTimeout(send, RETRY_MS);
  }

  // ETU-12 : « Aucune de ces réponses n'est correcte » exclut les autres cases. La cocher
  // décoche les autres ; cocher une autre case la décoche.
  function exclusive(target) {
    if (!inputs.includes(target) || !target.checked) return;
    const none = "none" in target.dataset;
    for (const input of inputs) {
      if (input !== target && "none" in input.dataset !== none) input.checked = false;
    }
  }

  function changed() {
    mark();
    updateTrace(slot, { given: chosen(), ok: false });
    show(TEXT.sending);
    send();
  }
  form.addEventListener("change", (event) => {
    exclusive(event.target);
    changed();
  });
  if (clear) {
    clear.addEventListener("click", () => {
      for (const input of inputs) input.checked = false;
      changed();
    });
  }

  // À l'échéance du téléphone, les propositions se verrouillent : plus aucun choix ne part. Une
  // réponse non confirmée est alors signalée comme non enregistrée, sauf si le serveur dit
  // l'avoir reçue à temps (sa confirmation s'était perdue). Si le serveur annonce ensuite du
  // temps ajouté (TPS-01), elles se déverrouillent, et l'envoi reprend.
  let over = false;
  setInterval(async () => {
    if (ended() === over) return;
    over = !over;
    fieldset.disabled = over;
    mark();
    const entry = readTrace()[slot];
    if (!entry || entry.ok) return;
    if (!over) {
      show(TEXT.sending);
      send();
      return;
    }
    clearTimeout(retry);
    let checked = null;
    try {
      checked = (await reconcile([slot]))[slot];
    } catch {
      // pas de réseau : le téléphone ne peut pas savoir
    }
    if (checked?.ok) show(checked.given.length ? saved : cleared);
    else show(tooLate);
  }, 250);

  // --- Au chargement : rechargement en cours d'envoi, créneaux précédents --------------------
  // Ce que le serveur a enregistré est ce que la page cochait à son arrivée (defaultChecked) :
  // un navigateur qui restaure l'état du formulaire au rechargement ne doit pas le masquer.
  const onServer = inputs
    .filter((input) => input.defaultChecked)
    .map((input) => Number(input.value))
    .sort((a, b) => a - b);
  const trace = readTrace();
  const entry = trace[slot];
  const pending = entry && !entry.ok && !same(entry.given, onServer);
  // Envoi encore en attente : le dernier choix est réaffiché et renvoyé (décision I11) ;
  // sinon, la réponse enregistrée (ETU-07).
  const shown = pending ? entry.given : onServer;
  for (const input of inputs) input.checked = shown.includes(Number(input.value));
  if (pending) changed();
  else {
    if (entry && !entry.ok) updateTrace(slot, { ok: true }); // le serveur l'a reçue
    mark();
  }
  // Réponse d'un créneau précédent jamais confirmée, et pas encore signalée : on demande au
  // serveur, puis on le dit sur cet écran, le premier qui suit (et sur lui seulement, s'il
  // est rechargé).
  const earlier = unconfirmed(trace, (other) => other < Number(slot)).filter((other) =>
    [undefined, slot].includes(trace[other].told),
  );
  if (earlier.length) {
    reconcileSoon(earlier).then((updated) => {
      if (updated === null) return;
      const lost = earlier.filter((other) => !updated[other].ok);
      if (lost.length === 0) return;
      for (const other of lost) updated[other].told = slot;
      writeTrace(updated);
      reveal(document.getElementById("previous-lost"), TEXT.previousLost);
    });
  }
})();
