const statuses = [
  { measure: 5, note: "G4", confidence: "0.78", pageTurn: "true" },
  { measure: 6, note: "A4", confidence: "0.81", pageTurn: "false" },
  { measure: 7, note: "B4", confidence: "0.83", pageTurn: "true" },
  { measure: 8, note: "C5", confidence: "0.83", pageTurn: "false" },
];

const measures = Array.from(document.querySelectorAll(".measure"));
const confidence = document.querySelector("#confidence-score");
const pageTurn = document.querySelector("#page-turn-signal");
const trackingStatus = document.querySelector("#tracking-status");
let activeIndex = 0;

function updateDemo() {
  const status = statuses[activeIndex];

  measures.forEach((measure, index) => {
    measure.classList.toggle("active", index === activeIndex);
  });

  trackingStatus.textContent = "locked";
  confidence.textContent = status.confidence;
  pageTurn.textContent = status.pageTurn;
  activeIndex = (activeIndex + 1) % statuses.length;
}

setInterval(updateDemo, 1600);

document.querySelector(".waitlist-form").addEventListener("submit", (event) => {
  event.preventDefault();
  event.currentTarget.querySelector("button").textContent = "Thanks";
});
