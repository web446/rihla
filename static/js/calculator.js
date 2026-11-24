/* Trip cost calculator on the country page.
 *
 * Every time the form changes, we ask the SERVER for the price with fetch()
 * (GET /api/estimate?...). The maths lives only in Python
 * (services/pricing.py -> estimate_trip_cost), so the calculator, the AI agent
 * and the bookings always agree. This file only sends the choices and shows
 * the answer.
 */
(function () {
  "use strict";

  const form = document.getElementById("calculator");
  if (!form) return; // not on a country page

  const linesList = document.getElementById("receipt-lines");
  const totalBox = document.getElementById("receipt-total");
  const flightSelect = document.getElementById("c-flight");
  let timer = null;        // for "debouncing" (wait until the user stops typing)
  let controller = null;   // lets us cancel an older request that is still loading

  // Build the URL: /api/estimate?country=turkey&flight_id=2&...&monument_ids=1,4
  function buildUrl() {
    const data = new FormData(form);
    const params = new URLSearchParams();
    params.set("country", form.dataset.country);
    for (const name of ["flight_id", "stay_id", "nights", "guide_id", "guide_days", "days", "travelers"]) {
      params.set(name, data.get(name) || "");
    }
    params.set("monument_ids", data.getAll("monument_ids").join(","));
    return form.dataset.api + "?" + params.toString();
  }

  // Show the receipt. textContent (not innerHTML) so no text can ever run as HTML.
  function render(estimate) {
    linesList.replaceChildren();
    if (estimate.lines.length === 0) {
      const li = document.createElement("li");
      li.className = "text-muted";
      li.textContent = "Choose a flight, a stay or a guide…";
      linesList.append(li);
    }
    for (const line of estimate.lines) {
      const li = document.createElement("li");
      const left = document.createElement("span");
      const label = document.createElement("strong");
      const detail = document.createElement("small");
      const right = document.createElement("span");
      label.textContent = line.label;
      detail.textContent = line.detail;
      right.textContent = line.total;
      left.append(label, document.createElement("br"), detail);
      li.append(left, right);
      linesList.append(li);
    }
    totalBox.textContent = estimate.total;
    totalBox.classList.remove("pulse");
    void totalBox.offsetWidth; // restart the CSS animation
    totalBox.classList.add("pulse");
  }

  async function update() {
    if (controller) controller.abort();
    controller = new AbortController();
    try {
      const response = await fetch(buildUrl(), { signal: controller.signal });
      if (!response.ok) throw new Error("HTTP " + response.status);
      render(await response.json());
    } catch (error) {
      if (error.name !== "AbortError") {
        totalBox.textContent = "Unavailable";
        console.error("Estimate failed:", error);
      }
    }
  }

  // Wait 250 ms after the last change before calling the server.
  function scheduleUpdate() {
    clearTimeout(timer);
    timer = setTimeout(update, 250);
  }

  // Choosing a flight fills in the nights and days of that round trip.
  flightSelect.addEventListener("change", function () {
    const option = flightSelect.selectedOptions[0];
    if (option && option.dataset.nights) {
      const nights = parseInt(option.dataset.nights, 10);
      form.elements.nights.value = nights;
      form.elements.days.value = nights + 1;
    }
  });

  form.addEventListener("input", scheduleUpdate);
  form.addEventListener("change", scheduleUpdate);
  form.addEventListener("submit", function (event) { event.preventDefault(); });
  update(); // first estimate when the page opens
})();
