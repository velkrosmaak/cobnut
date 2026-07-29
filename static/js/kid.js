/* Handles chore completion and fires the "token burst" animation.

   Written in a deliberately conservative style (var instead of let/const,
   function expressions instead of arrow functions, string concatenation
   instead of template literals, XMLHttpRequest instead of fetch/async) so
   it keeps working on older or embedded Chromium/WebKit browsers that lag
   behind desktop releases — for example the browser built into Samsung
   Family Hub smart fridges. */

(function () {
  "use strict";

  var tokenSrcEl = document.getElementById("token-image-source");
  var tokenSrc = tokenSrcEl ? tokenSrcEl.getAttribute("data-src") : "";
  var sparkColors = ["#ff5d8f", "#ffd166", "#2ec4b6", "#a06cd5", "#4cc9f0", "#4be389"];
  var sparkleColors = ["#fff9d6", "#ffe9a8", "#ffd6ef", "#d8f5ff", "#e3d6ff"];

  function rand(min, max) {
    return Math.random() * (max - min) + min;
  }

  function toArray(nodeList) {
    return Array.prototype.slice.call(nodeList);
  }

  function setVar(el, name, value) {
    // Standard API; supported on every browser new enough to run CSS custom
    // properties in the first place (which the animations already require).
    el.style.setProperty(name, value);
  }

  function removeEl(el) {
    if (el && el.parentNode) {
      el.parentNode.removeChild(el);
    }
  }

  function scheduleRemoval(el, ms) {
    // A plain timeout instead of relying on animationend firing correctly
    // across every engine (some embedded WebKit builds are inconsistent
    // about firing it for multi-animation shorthand). A little slack is
    // added so the slow fade is never cut short.
    setTimeout(function () {
      removeEl(el);
    }, ms + 150);
  }

  function getBurstLayer() {
    var layer = document.querySelector(".burst-layer");
    if (!layer) {
      layer = document.createElement("div");
      layer.className = "burst-layer";
      document.body.appendChild(layer);
    }
    return layer;
  }

  function fireBurst(originRect, tokenCount) {
    var layer = getBurstLayer();
    var originX = originRect.left + originRect.width / 2;
    var originY = originRect.top + originRect.height / 2;
    var i, angle, distance, dx, dy, size, el;

    // Two staggered expanding rings right at the button for extra punch.
    for (i = 0; i < 2; i++) {
      var ring = document.createElement("div");
      ring.className = i === 1 ? "ring-pulse ring-2" : "ring-pulse";
      var ringSize = 90;
      ring.style.width = ringSize + "px";
      ring.style.height = ringSize + "px";
      ring.style.left = (originX - ringSize / 2) + "px";
      ring.style.top = (originY - ringSize / 2) + "px";
      layer.appendChild(ring);
      scheduleRemoval(ring, 800);
    }

    // A big explosive scatter of token images, scaled with tokens earned.
    var total = Math.min(Math.max(tokenCount * 4, 18), 32);
    for (i = 0; i < total; i++) {
      if (tokenSrc) {
        el = document.createElement("img");
        el.src = tokenSrc;
        el.className = "burst-token";
      } else {
        el = document.createElement("div");
        el.className = "burst-token burst-spark";
        el.style.background = sparkColors[i % sparkColors.length];
      }
      angle = rand(-200, 20);
      distance = rand(180, 480);
      dx = Math.cos((angle * Math.PI) / 180) * distance;
      dy = Math.sin((angle * Math.PI) / 180) * distance;
      setVar(el, "--dx", dx + "px");
      setVar(el, "--dy", dy + "px");
      setVar(el, "--rot", rand(-420, 420) + "deg");
      size = rand(30, 48);
      el.style.width = size + "px";
      el.style.height = size + "px";
      el.style.left = (originX - size / 2) + "px";
      el.style.top = (originY - size / 2) + "px";
      el.style.animationDelay = rand(0, 140) + "ms";
      el.style.webkitAnimationDelay = el.style.animationDelay;
      layer.appendChild(el);
      scheduleRemoval(el, 3300);
    }

    // Confetti sparks, scattering the full circle.
    for (i = 0; i < 16; i++) {
      var spark = document.createElement("div");
      spark.className = "burst-spark";
      spark.style.background = sparkColors[i % sparkColors.length];
      angle = rand(0, 360);
      distance = rand(120, 340);
      setVar(spark, "--dx", (Math.cos((angle * Math.PI) / 180) * distance) + "px");
      setVar(spark, "--dy", (Math.sin((angle * Math.PI) / 180) * distance) + "px");
      setVar(spark, "--rot", rand(-360, 360) + "deg");
      spark.style.left = (originX - 5) + "px";
      spark.style.top = (originY - 5) + "px";
      spark.style.animationDelay = rand(0, 100) + "ms";
      spark.style.webkitAnimationDelay = spark.style.animationDelay;
      layer.appendChild(spark);
      scheduleRemoval(spark, 2700);
    }

    // Twinkling sparkles for shine.
    for (i = 0; i < 14; i++) {
      var sparkle = document.createElement("div");
      sparkle.className = "burst-sparkle";
      setVar(sparkle, "--sparkle-color", sparkleColors[i % sparkleColors.length]);
      angle = rand(-210, 30);
      distance = rand(140, 400);
      setVar(sparkle, "--dx", (Math.cos((angle * Math.PI) / 180) * distance) + "px");
      setVar(sparkle, "--dy", (Math.sin((angle * Math.PI) / 180) * distance) + "px");
      setVar(sparkle, "--rot", rand(-180, 180) + "deg");
      sparkle.style.left = (originX - 9) + "px";
      sparkle.style.top = (originY - 9) + "px";
      sparkle.style.animationDelay = rand(0, 180) + "ms";
      sparkle.style.webkitAnimationDelay = sparkle.style.animationDelay;
      layer.appendChild(sparkle);
      scheduleRemoval(sparkle, 3000);
    }
  }

  function popBalance(newValue) {
    var numberEl = document.getElementById("balance-number");
    if (!numberEl) return;
    numberEl.textContent = newValue;
    numberEl.className = numberEl.className.replace(/\bbalance-pop\b/g, "").trim();
    // force reflow so the animation can replay
    void numberEl.offsetWidth;
    numberEl.className = (numberEl.className + " balance-pop").trim();
  }

  function postComplete(url, onSuccess, onError) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4) {
        if (xhr.status >= 200 && xhr.status < 300) {
          var data;
          try {
            data = JSON.parse(xhr.responseText);
          } catch (e) {
            onError();
            return;
          }
          onSuccess(data);
        } else {
          onError();
        }
      }
    };
    xhr.onerror = onError;
    xhr.send();
  }

  function shakeButton(button) {
    button.className = button.className.replace(/\bshake\b/g, "").trim();
    void button.offsetWidth;
    button.className = (button.className + " shake").trim();
  }

  toArray(document.querySelectorAll(".complete-form")).forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var button = form.querySelector("button");
      if (button.disabled) return;

      var rect = button.getBoundingClientRect();

      postComplete(
        form.getAttribute("action"),
        function (data) {
          if (data.status === "completed") {
            fireBurst(rect, data.tokens_awarded);
            popBalance(data.balance);

            button.disabled = true;
            button.className = (button.className + " done").trim();
            button.textContent = "Done — resets " + form.getAttribute("data-reset-label");
            var card = form.parentNode;
            while (card && card.className.indexOf("chore-card") === -1) {
              card = card.parentNode;
            }
            if (card) {
              card.className = (card.className + " done").trim();
            }
          } else if (data.status === "already_done") {
            shakeButton(button);
          }
        },
        function () {
          // Fall back to a normal form submit if the request failed for any reason.
          form.submit();
        }
      );
    });
  });
})();
