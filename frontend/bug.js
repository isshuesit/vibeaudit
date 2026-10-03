/* ============================================================
   Audit bug — a small recurring investigator that lives in the
   lower-right margin of VIBEAUDIT.

   It observes state emitted on window.VibeBugBus (see app.js). It
   never computes scores, never invents findings, and only comments
   on values that are actually present in the audit result.

   Pieces:
     MESSAGES          - pools of lines per context
     DISCOVERIES       - methodology concepts, unlocked by behaviour
     engine            - anti-repetition weighted selection
     view              - the specimen + speech bubble
     controller        - idle life + bus wiring
   ============================================================ */

(function () {
  "use strict";

  var bus = window.VibeBugBus;
  if (!bus) return;

  var reduceMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --------------------------------------------------------
     1. MESSAGE LIBRARY
     Backticked `tokens` render in IBM Plex Mono.
     -------------------------------------------------------- */

  var MESSAGES = {
    NAV_SINGLE: [
      "One target at a time. Less chaos.",
      "Single audit. Intimate.",
      "One website. One set of problems.",
      "Let's inspect one before we get ambitious.",
      "Single-target mode. Sensible.",
      "One site. I can watch that one closely.",
    ],
    NAV_BATCH: [
      "Batch mode. Because apparently one website wasn't enough.",
      "Several targets. I hope someone brought patience.",
      "Batch audit. Efficient, assuming the servers cooperate.",
      "More websites, more data, same small bug.",
      "Requests are spaced out on purpose. Even websites deserve personal space.",
      "A queue of sites. I'll pace myself.",
    ],
    NAV_LEADERBOARD: [
      "Comparisons are useful. Assuming we're comparing the same thing.",
      "Here is where everyone's numbers become suspiciously competitive.",
      "Rankings. Humans do love a hierarchy.",
      "`TSGA` is built for comparison. It is not a universal measure of goodness.",
      "A table of gaps. Interesting, if you remember what the gap measures.",
      "History, sorted. Sorting adds order, not meaning.",
    ],
    NAV_METHOD: [
      "Here is where the numbers explain themselves.",
      "The methodology lives here. Try not to skip it.",
      "Numbers without definitions are just decorative confidence.",
      "Before trusting the score, understand what it measures.",
      "Yes, there is documentation. Tragic but necessary.",
      "Read this part. It is the part that keeps the rest honest.",
    ],

    AUDIT_START: [
      "Inspecting.",
      "Let's see what the site is actually doing.",
      "Beginning audit. Try not to influence the results.",
      "Time to collect evidence.",
      "Fetching the boring stuff.",
      "Let's see what survives contact with the scanner.",
      "Investigating.",
      "Looking now.",
    ],
    AUDIT_COMPLETE: [
      "Audit complete.",
      "Evidence collected.",
      "That is what the scanner found. Interpretation is your department.",
      "Done. Now the numbers have opinions.",
      "Audit complete. Interpretation remains everyone's favourite problem.",
      "Finished. Read the methodology before declaring anything.",
      "Collected. A score still needs a reader.",
    ],
    AUDIT_FAIL: [
      "The fetch did not complete. That is a finding too.",
      "No response worth scoring. Sometimes the target simply declines.",
      "Audit failed. The absence of data is still data, technically.",
      "Nothing came back. Worth trying again, or noting the silence.",
      "The target did not cooperate.",
    ],
    INVALID_TARGET: [
      "That does not look like a URL I can reach.",
      "The address needs an `http://` or `https://` on the front.",
      "I can only inspect public web addresses. This one did not qualify.",
      "Refused before fetching. Check the target.",
    ],

    HTTPS_FOUND: [
      "`HTTPS` detected. Good. The boring stuff matters.",
      "Encrypted transport. We may proceed.",
      "`HTTPS` is doing its quiet little job.",
      "The connection is protected. Sensible.",
      "`HTTPS` present. Necessary, not sufficient, but present.",
      "Transport is encrypted. One fewer thing to worry about.",
    ],
    HTTPS_ABSENT: [
      "No `HTTPS`. The connection is in the open.",
      "Served over plain `http`. Everything in transit is readable.",
      "`HTTPS` is missing. That is not a small detail.",
      "Unencrypted transport. Worth noticing before anything else.",
      "No transport security detected here.",
    ],
    PRIVACY_FOUND: [
      "A privacy-policy link is present. A low bar, cleared.",
      "Privacy policy: linked. Whether anyone reads it is another matter.",
      "Privacy-policy link detected.",
      "There is a privacy policy to point at, at least.",
    ],
    PRIVACY_MISSING: [
      "No privacy-policy link detected. Worth noticing.",
      "Privacy policy: apparently taking the day off.",
      "No privacy-policy link found.",
      "The privacy link appears to be missing.",
      "Nothing here points me toward a privacy policy.",
      "No privacy-policy link. An observation, not an accusation.",
    ],
    HEADERS_COMPLETE: [
      "Five security headers. Boring is underrated.",
      "`5/5`. Someone remembered the boring parts.",
      "The expected security headers are all present.",
      "Five out of five. The unglamorous work was done.",
      "Full set of response headers. Civilisation continues.",
    ],
    HEADERS_PARTIAL: [
      "Not all the expected headers are here.",
      "Some of the defensive furniture is missing.",
      "Partial header coverage. Some mitigations, not all.",
      "A few of the security headers did not show up.",
      "Header set is incomplete. Note which ones.",
    ],
    HEADERS_NONE: [
      "None of the expected security headers responded.",
      "No security headers at all. That is a gap in itself.",
      "The defensive headers are simply absent here.",
      "Zero of the checked headers present.",
    ],
    UTST_ZERO: [
      "No trust-inflation patterns detected.",
      "Nothing suspicious in the trust-signalling layer.",
      "`UTST` is zero. An absence of detected inflation, not a certificate of virtue.",
      "No automated trust-inflation signals showed up.",
      "Nothing here appears to be inflating trust automatically.",
      "Zero detected signals. Not zero trustworthiness. Different claim.",
    ],
    UTST_LOW: [
      "A trust signal or two. Mild.",
      "Small `UTST`. Something is doing a little credibility work.",
      "A couple of patterns fired. Not alarming, worth a look.",
      "Low trust-signal count. Read what actually matched.",
    ],
    UTST_MODERATE: [
      "A moderate `UTST`. The site is working on how trustworthy it looks.",
      "Several trust signals detected. Not malicious by default. Worth examining.",
      "The credibility layer is fairly busy here.",
      "Mid-range `UTST`. Check the matched patterns before judging.",
    ],
    UTST_HIGH: [
      "High `UTST`. Something here is trying quite hard to look trustworthy.",
      "A lot of trust signalling. A prompt for manual review, not a verdict.",
      "The trust-signal count is high. Read every matched line.",
      "Heavy credibility work detected. Intent is still yours to determine.",
    ],
    GAP_NEGATIVE: [
      "Negative gap. Security posture is keeping pace with the trust signalling.",
      "Gap is below zero. Remember what the gap measures before relaxing.",
      "The posture outweighs the signalling here. The healthy direction.",
      "Low gap. It means the two measures are close, nothing more.",
    ],
    GAP_NEAR_ZERO: [
      "The gap is near zero. Signalling and posture are roughly matched.",
      "Balanced gap. Neither measure is running ahead.",
      "Gap close to zero. Unremarkable, which is fine.",
    ],
    GAP_POSITIVE: [
      "Positive gap. Trust signalling is running ahead of security posture.",
      "The gap leans positive. The direction worth investigating.",
      "Signalling outpaces posture here. Note it, then check why.",
      "Gap above zero. The look is ahead of the substance, by this measure.",
    ],
    BLANK_PAGE: [
      "Almost no readable text. The page likely renders in the browser, and the scanner does not.",
      "Near-empty result. That describes the delivered HTML, not the rendered app.",
      "This looks JavaScript-rendered. Treat the blank as a finding, not an error.",
      "Little to read here without executing scripts. Noted as such.",
    ],
    HRI_UNASSESSED: [
      "`HRI` is still unjudged. I am a bug, not a mind reader.",
      "Human risk remains unanswered. Conveniently, I am not human.",
      "`HRI` has not been assessed yet.",
      "Apparently this part still requires a human.",
      "No `HRI` judgement yet. My tiny legs are not qualified.",
      "Habituation risk: unset. The multiplier is sitting at one.",
    ],
    HRI_ADJUSTED: [
      "Human judgement just entered the equation.",
      "Now we are letting a human make a judgement. Brave.",
      "`HRI` set. The machines have been demoted slightly.",
      "A human weighed in on the risk. The number moved accordingly.",
      "Manual judgement applied. The part detection cannot do responsibly.",
      "`HRI` adjusted. It multiplies the gap, it does not replace it.",
    ],
    LEADERBOARD_REFRESH: [
      "Refreshed. Same records, freshly fetched.",
      "Reloaded the history. Nothing new invents itself.",
      "Refresh done. The table is current.",
      "Pulled the latest. Still the same set of gaps.",
    ],
    LEADERBOARD_SORT: [
      "Re-sorted. Order changed, meaning did not.",
      "Sorting rearranges rows. It does not rank importance.",
      "New sort key. The numbers underneath are unchanged.",
      "Sorted. A different view of the same data.",
    ],
    LEADERBOARD_EMPTY: [
      "Nothing recorded yet. Run an audit and this fills in.",
      "Empty history. The table is waiting.",
      "No records. Comparisons need something to compare.",
    ],
    BATCH_START: [
      "Batch started. I will watch them go past.",
      "Queue running. Politely paced, as intended.",
      "Several fetches, one at a time. Give it a moment.",
      "Collecting evidence in bulk.",
    ],
    BATCH_MULTI: [
      "More than one target. The spacing between requests is deliberate.",
      "A list of sites. Each gets the same checks, which is the point.",
      "Multiple targets. Comparable only because the method is identical.",
    ],
    BATCH_COMPLETE: [
      "Batch complete. The summary is a starting point, not a conclusion.",
      "All done. Read the per-row detail before trusting the averages.",
      "Finished the queue. Averages hide the interesting rows.",
      "Batch collected. Interpretation still does not scale.",
    ],
    BATCH_PARTIAL_FAIL: [
      "Some targets did not respond. The failures are in the table too.",
      "Part of the batch failed to fetch. Note which before averaging.",
      "A few fetches came back empty. That is data, not noise.",
    ],
  };

  /* --------------------------------------------------------
     2. DISCOVERY LIBRARY
     -------------------------------------------------------- */

  var DISCOVERIES = [
    { id: "trust-neq-security", title: "Trust ≠ security",
      blurb: "A site can be technically well-secured and still lean on persuasive or manipulative trust signals. The two are measured separately.",
      trigger: "first-audit" },
    { id: "scores-need-context", title: "Scores need context",
      blurb: "A score means something only once you know what was measured and how it was normalised.",
      trigger: "first-method" },
    { id: "manual-judgement", title: "Manual judgement",
      blurb: "Some dimensions — habituation risk among them — are not responsibly reducible to automated detection, so a human sets them.",
      trigger: "first-hri" },
    { id: "what-is-utst", title: "UTST",
      blurb: "UTST is the weighted count of detected trust-signalling patterns in the page text. It records detection, not intent.",
      trigger: "first-nonzero-utst" },
    { id: "comparisons-need-consistency", title: "Comparisons need consistency",
      blurb: "Ranked TSGA values only compare cleanly when the same checks and normalisation produced every one of them.",
      trigger: "first-leaderboard" },
    { id: "request-spacing", title: "Request spacing",
      blurb: "Batch requests are spaced out on purpose. Auditing politely is part of the method, not a delay bug.",
      trigger: "first-batch" },
    { id: "absence-not-evidence", title: "Absence ≠ evidence",
      blurb: "Not finding a privacy-policy link is a recorded observation, not proof that no policy exists.",
      trigger: "first-privacy-missing" },
    { id: "defensive-layers", title: "Defensive layers",
      blurb: "Security headers are independent mitigations. A partial set means some defensive furniture is simply absent.",
      trigger: "first-headers-partial" },
    { id: "transport-security", title: "Transport security",
      blurb: "HTTPS protects data in transit. Its presence is necessary, not sufficient, and it says nothing about the site's content.",
      trigger: "first-https-absent" },
    { id: "zero-isnt-proof", title: "Zero isn't proof",
      blurb: "A UTST of zero means no automated pattern fired. It is an absence of detected inflation, not a certificate of virtue.",
      trigger: "first-utst-zero" },
    { id: "what-is-the-gap", title: "The gap",
      blurb: "The gap subtracts normalised security posture from normalised trust signalling. Negative means posture is keeping pace.",
      trigger: "audit-count-2" },
    { id: "what-is-spc", title: "SPC",
      blurb: "SPC is the observed security posture: HTTPS, a privacy-policy link, and the security response headers that were present.",
      trigger: "audit-count-3" },
    { id: "normalisation", title: "Normalisation",
      blurb: "Raw subtotals are scaled against the maximum the automated checks could produce, so the headline number is bounded, not absolute truth.",
      trigger: "audit-count-6" },
    { id: "rendered-vs-delivered", title: "Rendered vs delivered",
      blurb: "The scanner reads delivered HTML and does not run JavaScript. A near-empty result describes the fallback content, not the rendered app.",
      trigger: "first-blank-page" },
    { id: "bands-are-thresholds", title: "Bands are thresholds",
      blurb: "Low, Moderate, High and Severe are cut-points on the gap, not moral categories. Read the number underneath.",
      trigger: "first-high-band" },
    { id: "different-questions", title: "Different questions",
      blurb: "Technical protection and perceived credibility answer different questions. VIBEAUDIT reports both and leaves the synthesis to you.",
      trigger: "first-sort" },
  ];

  /* --------------------------------------------------------
     3. MESSAGE ENGINE — weighted, anti-repetition
     -------------------------------------------------------- */

  var engine = (function () {
    var RECENT_IDS = [];
    var RECENT_IDS_MAX = 16;
    var RECENT_CATS = [];
    var RECENT_CATS_MAX = 4;
    var cooldownUntil = {};
    var ID_COOLDOWN = 130000;

    function pool(cat) {
      var arr = MESSAGES[cat] || [];
      return arr.map(function (text, i) {
        return { id: cat + "#" + i, cat: cat, text: text };
      });
    }

    function pick(cats) {
      var now = Date.now();
      var cands = [];
      cats.forEach(function (cat, ci) {
        var base = cats.length - ci; // earlier category => higher base weight
        pool(cat).forEach(function (m) {
          if (RECENT_IDS.indexOf(m.id) !== -1) return;
          if ((cooldownUntil[m.id] || 0) > now) return;
          var w = base;
          if (RECENT_CATS.indexOf(m.cat) !== -1) w *= 0.18;
          cands.push({ m: m, w: w });
        });
      });

      if (!cands.length) {
        // everything recently used: relax cooldown but never repeat the very last line
        var last = RECENT_IDS[RECENT_IDS.length - 1];
        cats.forEach(function (cat, ci) {
          var base = cats.length - ci;
          pool(cat).forEach(function (m) {
            if (m.id === last) return;
            cands.push({ m: m, w: base });
          });
        });
      }
      if (!cands.length) return null;

      var total = cands.reduce(function (s, c) { return s + c.w; }, 0);
      var r = Math.random() * total;
      var chosen = cands[cands.length - 1].m;
      for (var i = 0; i < cands.length; i++) {
        r -= cands[i].w;
        if (r <= 0) { chosen = cands[i].m; break; }
      }

      RECENT_IDS.push(chosen.id);
      while (RECENT_IDS.length > RECENT_IDS_MAX) RECENT_IDS.shift();
      RECENT_CATS.push(chosen.cat);
      while (RECENT_CATS.length > RECENT_CATS_MAX) RECENT_CATS.shift();
      cooldownUntil[chosen.id] = now + ID_COOLDOWN;
      return chosen.text;
    }

    return { pick: pick };
  })();

  /* --------------------------------------------------------
     4. VIEW — the specimen and its speech bubble
     -------------------------------------------------------- */

  var SVG =
    '<svg class="bug-figure" viewBox="0 0 96 96" fill="none" stroke="currentColor" ' +
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<g class="bug-farside">' +
    '<path d="M40 46 L36 34 L30 30"/><path d="M52 47 L52 33 L47 28"/><path d="M63 49 L69 38 L67 31"/>' +
    "</g>" +
    '<path d="M38 60 L30 72 L22 75"/><path d="M50 63 L47 79 L38 84"/><path d="M62 62 L66 77 L60 83"/>' +
    '<ellipse cx="57" cy="55" rx="25" ry="17"/>' +
    '<path d="M45 41 Q57 47 68 42"/><path d="M43 56 Q57 62 71 55"/>' +
    '<ellipse cx="34" cy="52" rx="8.5" ry="7.5"/>' +
    '<circle cx="22" cy="49" r="7"/>' +
    '<circle class="bug-eye" cx="19" cy="47" r="1.7" fill="currentColor" stroke="none"/>' +
    '<circle class="bug-eye" cx="23" cy="50" r="1.5" fill="currentColor" stroke="none"/>' +
    '<path class="bug-ant-l" d="M18 44 Q11 33 13 24"/>' +
    '<path class="bug-ant-r" d="M21 43 Q17 31 21 22"/>' +
    '<circle cx="13" cy="24" r="1.1" fill="currentColor" stroke="none"/>' +
    '<circle cx="21" cy="22" r="1.1" fill="currentColor" stroke="none"/>' +
    '<g class="bug-lens-grp"><circle cx="15" cy="74" r="5.5"/><path d="M19 78 L25 84"/></g>' +
    "</svg>";

  var view = (function () {
    var root = document.createElement("div");
    root.className = "bug-root";
    root.innerHTML = SVG + '<div class="bug-bubble" role="status" aria-live="polite"></div>';
    var bubble = root.querySelector(".bug-bubble");
    var hideTimer = null;
    var poseTimer = null;

    function mount() { document.body.appendChild(root); }
    function enter() { root.classList.add("is-in"); }
    function setHidden(h) { root.classList.toggle("is-hidden", !!h); }
    function isHidden() { return root.classList.contains("is-hidden"); }
    function isSpeaking() { return bubble.classList.contains("is-open"); }

    function pose(name, ms) {
      if (reduceMotion) return;
      clearTimeout(poseTimer);
      Array.prototype.slice.call(root.classList).forEach(function (c) {
        if (c.indexOf("pose-") === 0) root.classList.remove(c);
      });
      root.classList.add("pose-" + name, "is-active");
      poseTimer = setTimeout(function () {
        root.classList.remove("pose-" + name, "is-active");
      }, ms || 700);
    }

    function cancel() { clearTimeout(hideTimer); }

    function speak(html, opts) {
      opts = opts || {};
      bubble.innerHTML = html;
      bubble.classList.add("is-open");
      root.classList.add("is-speaking");
      pose(opts.pose || "turn", 620);
      clearTimeout(hideTimer);
      hideTimer = setTimeout(function () {
        hide();
        if (typeof opts.onDone === "function") opts.onDone();
      }, opts.duration || 4200);
    }

    function hide() {
      bubble.classList.remove("is-open");
      root.classList.remove("is-speaking");
    }

    return {
      root: root, mount: mount, enter: enter, setHidden: setHidden,
      isHidden: isHidden, isSpeaking: isSpeaking, pose: pose,
      speak: speak, hide: hide, cancel: cancel,
    };
  })();

  /* --------------------------------------------------------
     5. CONTROLLER — idle life, discoveries, bus wiring
     -------------------------------------------------------- */

  var started = false;
  var lastBubbleEndedAt = 0;
  var currentPriority = 0;
  var MIN_GAP = 5200;

  var auditCount = 0;
  var unlocked = {};              // discovery id -> true (session only)
  var unlockedCount = 0;
  var discoveryQueue = [];
  var activeDiscovery = null;     // discovery whose bubble is on screen now
  var lastDiscoveryAt = 0;
  var lastAuditEventAt = 0;
  var DISCOVERY_GAP = 32000;
  var DISCOVERY_PRIORITY = 3;     // findings (4) can interrupt a concept; nav (2) cannot
  var seenViews = {};
  var idleTimer = null;
  var awayTimer = null;

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function totalDiscoveries() { return DISCOVERIES.length; }

  function esc(s) {
    return String(s).replace(/[&<>]/g, function (c) {
      return c === "&" ? "&amp;" : c === "<" ? "&lt;" : "&gt;";
    });
  }
  function renderText(t) {
    return esc(t).replace(/`([^`]+)`/g, '<span class="k">$1</span>');
  }
  function clampDur(t) {
    return Math.max(3200, Math.min(7000, 2600 + t.length * 42));
  }

  function overlayOpen() {
    var o = document.getElementById("noise-overlay");
    return o && !o.hidden;
  }

  function canSpeak(priority) {
    if (!started || overlayOpen()) return false;
    if (view.isSpeaking()) return priority > currentPriority;
    // Findings (>= 4) are the point of the tool: let them through as soon as
    // the screen is clear. Lower-priority chatter waits out a quiet gap.
    var gap = priority >= 4 ? 0 : MIN_GAP;
    return Date.now() - lastBubbleEndedAt >= gap;
  }

  function wake() {
    clearTimeout(awayTimer);
    view.setHidden(false);
  }

  function say(cats, priority, opts) {
    opts = opts || {};
    if (!canSpeak(priority)) return false;
    var list = Array.isArray(cats) ? cats : [cats];
    var text = engine.pick(list);
    if (!text) return false;

    function run() {
      wake();
      currentPriority = priority;
      var dur = opts.duration || clampDur(text);
      view.speak(renderText(text), {
        pose: opts.pose,
        duration: dur,
        onDone: function () {
          lastBubbleEndedAt = Date.now();
          currentPriority = 0;
          if (opts.follow && opts.follow.length && Math.random() < 0.16) {
            setTimeout(function () {
              say(opts.follow, 4, {});
            }, 900 + Math.random() * 700);
          }
          setTimeout(drainDiscovery, 450);
        },
      });
    }

    if (view.isSpeaking()) {
      // interrupting a concept in progress: put it back at the front of the
      // queue so the teaching is not simply lost.
      if (currentPriority === DISCOVERY_PRIORITY && activeDiscovery) {
        discoveryQueue.unshift(activeDiscovery);
        activeDiscovery = null;
        lastDiscoveryAt = 0;
      }
      view.cancel();
      view.hide();
      setTimeout(run, 240);
    } else {
      run();
    }
    return true;
  }

  /* ---- discoveries ---- */

  function mountCounter() {
    var host = document.querySelector("#panel-about .about-content");
    if (!host || host.querySelector(".bug-dcount")) return;
    var p = document.createElement("p");
    p.className = "bug-dcount";
    host.appendChild(p);
    updateCounter();
  }
  function updateCounter() {
    var p = document.querySelector(".bug-dcount");
    if (p) {
      p.textContent =
        pad(unlockedCount) + " / " + pad(totalDiscoveries()) + " concepts noted";
    }
  }

  function unlock(trigger) {
    var d = null;
    for (var i = 0; i < DISCOVERIES.length; i++) {
      if (DISCOVERIES[i].trigger === trigger && !unlocked[DISCOVERIES[i].id]) {
        d = DISCOVERIES[i];
        break;
      }
    }
    if (!d) return;
    unlocked[d.id] = true;
    unlockedCount++;
    updateCounter();
    // Cap the announce backlog so a burst of unlocks never becomes a lecture.
    // Overflow concepts stay counted; the user just doesn't get a bubble for them.
    if (discoveryQueue.length < 6) discoveryQueue.push(d);
    drainDiscovery();
  }

  function drainDiscovery() {
    if (!started || !discoveryQueue.length) return;
    if (overlayOpen() || view.isSpeaking()) return;
    var now = Date.now();
    if (now - lastDiscoveryAt < DISCOVERY_GAP) return;
    if (now - lastBubbleEndedAt < 2500) return;
    if (now - lastAuditEventAt < 4000) return; // never elbow into an audit

    var d = discoveryQueue.shift();
    activeDiscovery = d;
    lastDiscoveryAt = now;
    currentPriority = DISCOVERY_PRIORITY;
    wake();

    var html =
      '<span class="bug-kicker">New discovery &middot; ' +
      pad(unlockedCount) + " / " + pad(totalDiscoveries()) + "</span>" +
      '<span class="bug-title">' + esc(d.title) + "</span>" +
      '<span class="bug-blurb">' + esc(d.blurb) + "</span>";

    view.speak(html, {
      pose: "inspect",
      duration: Math.max(6000, Math.min(9200, 3800 + d.blurb.length * 34)),
      onDone: function () {
        activeDiscovery = null;
        lastBubbleEndedAt = Date.now();
        currentPriority = 0;
        setTimeout(drainDiscovery, 700);
      },
    });
  }

  /* ---- idle life ---- */

  function idleTick() {
    if (!started) { scheduleIdle(); return; }
    if (!view.isHidden() && !view.isSpeaking() && !overlayOpen()) {
      if (Math.random() < 0.14) {
        view.setHidden(true);
        clearTimeout(awayTimer);
        awayTimer = setTimeout(function () {
          view.setHidden(false);
        }, 9000 + Math.random() * 11000);
      } else if (!reduceMotion) {
        var moves = ["glance-left", "glance-right", "step", "hop", "inspect"];
        view.pose(moves[Math.floor(Math.random() * moves.length)], 900);
      }
    }
    // a quiet moment is also a chance to surface a pending concept
    drainDiscovery();
    scheduleIdle();
  }
  function scheduleIdle() {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(idleTick, 15000 + Math.random() * 16000);
  }

  /* ---- start ---- */

  function start() {
    if (started) return;
    started = true;
    view.enter();
    mountCounter();
    scheduleIdle();
  }

  view.mount();
  setTimeout(start, reduceMotion ? 400 : 1800);

  /* ---- bus wiring ---- */

  var NAV_CAT = {
    single: "NAV_SINGLE",
    batch: "NAV_BATCH",
    leaderboard: "NAV_LEADERBOARD",
    about: "NAV_METHOD",
  };

  bus.on("view:change", function (d) {
    var v = d && d.view;
    var cat = NAV_CAT[v];
    if (!cat) return;
    var firstTime = !seenViews[v];
    seenViews[v] = true;
    if (v === "about") unlock("first-method");
    if (v === "leaderboard") unlock("first-leaderboard");
    if (firstTime || Math.random() < 0.7) {
      say(cat, 2, { pose: "glance-left" });
    }
  });

  bus.on("audit:start", function () {
    lastAuditEventAt = Date.now();
    say("AUDIT_START", 3, { pose: "inspect", duration: 2600 });
  });

  bus.on("audit:error", function (d) {
    lastAuditEventAt = Date.now();
    if (d && d.batch) return;
    say(["INVALID_TARGET", "AUDIT_FAIL"], 4, { pose: "glance-right" });
  });

  bus.on("audit:complete", function (r) {
    lastAuditEventAt = Date.now();
    auditCount++;
    if (!r || !r.fetch_ok) {
      unlock("first-audit");
      say(["AUDIT_FAIL"], 4, { pose: "glance-right" });
      return;
    }

    var spc = r.spc || {};
    var utst = r.utst || {};
    var tsga = r.tsga || {};
    var present = (spc.security_headers_present || []).length;
    var checked = (spc.security_headers_checked || []).length || 5;
    var sub = utst.automated_subtotal || 0;

    // discovery triggers (only conditions the result actually contains)
    unlock("first-audit");
    if (auditCount === 2) unlock("audit-count-2");
    if (auditCount === 3) unlock("audit-count-3");
    if (auditCount === 6) unlock("audit-count-6");
    if (sub > 0) unlock("first-nonzero-utst");
    else unlock("first-utst-zero");
    if (!spc.privacy_policy_link_found) unlock("first-privacy-missing");
    if (present < checked) unlock("first-headers-partial");
    if (!spc.https) unlock("first-https-absent");
    if (r.likely_blank_page) unlock("first-blank-page");
    if (tsga.band_label === "High" || tsga.band_label === "Severe") unlock("first-high-band");

    // contextual observation categories, weighted (findings before positives)
    var obs = [];
    if (r.likely_blank_page) obs.push(["BLANK_PAGE", 6]);
    if (!spc.privacy_policy_link_found) obs.push(["PRIVACY_MISSING", 5]);
    if (!spc.https) obs.push(["HTTPS_ABSENT", 5]);
    if (present === 0) obs.push(["HEADERS_NONE", 4]);
    else if (present < checked) obs.push(["HEADERS_PARTIAL", 4]);
    if (sub >= 10) obs.push(["UTST_HIGH", 4]);
    else if (sub >= 5) obs.push(["UTST_MODERATE", 3]);
    else if (sub >= 1) obs.push(["UTST_LOW", 3]);
    if (tsga.hri_source === "not_assessed") obs.push(["HRI_UNASSESSED", 3]);
    if (spc.https) obs.push(["HTTPS_FOUND", 2]);
    if (present === checked && checked > 0) obs.push(["HEADERS_COMPLETE", 2]);
    if (sub === 0) obs.push(["UTST_ZERO", 2]);
    if (spc.privacy_policy_link_found) obs.push(["PRIVACY_FOUND", 1]);
    if (typeof tsga.gap === "number") {
      if (tsga.gap <= -1.5) obs.push(["GAP_NEGATIVE", 2]);
      else if (tsga.gap >= 1.5) obs.push(["GAP_POSITIVE", 2]);
      else obs.push(["GAP_NEAR_ZERO", 1]);
    }
    obs.push(["AUDIT_COMPLETE", 1]);

    // weighted pick of ONE lead category; the rest become fall-through / follow-up
    var totalW = obs.reduce(function (s, o) { return s + o[1]; }, 0);
    var rr = Math.random() * totalW;
    var idx = 0;
    for (var i = 0; i < obs.length; i++) {
      rr -= obs[i][1];
      if (rr <= 0) { idx = i; break; }
    }
    var ordered = [obs[idx][0]];
    var rest = [];
    obs.forEach(function (o, i) { if (i !== idx) { ordered.push(o[0]); rest.push(o[0]); } });

    say(ordered, 4, { pose: "inspect", follow: rest.slice(0, 3) });
  });

  bus.on("hri:change", function () {
    unlock("first-hri");
    say("HRI_ADJUSTED", 2, { pose: "glance-right" });
  });
  bus.on("hri:clear", function () {
    say("HRI_UNASSESSED", 2, {});
  });

  bus.on("batch:start", function (d) {
    lastAuditEventAt = Date.now();
    var many = d && d.count > 1;
    say(many ? ["BATCH_MULTI", "BATCH_START"] : ["BATCH_START"], 3, {
      pose: "inspect", duration: 3000,
    });
  });
  bus.on("batch:complete", function (s) {
    lastAuditEventAt = Date.now();
    unlock("first-batch");
    var partial = s && s.failed > 0;
    say(partial ? ["BATCH_PARTIAL_FAIL", "BATCH_COMPLETE"] : ["BATCH_COMPLETE"], 4, {
      pose: "inspect",
    });
  });

  bus.on("leaderboard:refresh", function () {
    say("LEADERBOARD_REFRESH", 2, {});
  });
  bus.on("leaderboard:sort", function () {
    unlock("first-sort");
    say("LEADERBOARD_SORT", 2, {});
  });
  bus.on("leaderboard:loaded", function (d) {
    unlock("first-leaderboard");
    if (d && d.count === 0) say("LEADERBOARD_EMPTY", 2, {});
  });
})();
