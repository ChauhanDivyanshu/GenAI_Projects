// chrome_extension/content.js
// Google Meet page par inject hota hai

(function () {
  "use strict";

  const SERVER_URL = "http://localhost:5000";
  let isMonitoring = false;
  let meetingId = null;

  // Tab switch detection
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && isMonitoring) {
      fetch(`${SERVER_URL}/api/cheating/tab-switch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meeting_id: meetingId }),
      }).catch(console.error);
    }
  });

  // Copy-paste detection
  document.addEventListener("copy", (e) => {
    if (isMonitoring) {
      const text = window.getSelection().toString();
      fetch(`${SERVER_URL}/api/cheating/copy-paste`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          meeting_id: meetingId,
          content: text,
        }),
      }).catch(console.error);
    }
  });

  // Right-click detection
  document.addEventListener("contextmenu", (e) => {
    if (isMonitoring) {
      fetch(`${SERVER_URL}/api/cheating/tab-switch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          meeting_id: meetingId,
          type: "right_click",
        }),
      }).catch(console.error);
    }
  });

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "start_monitoring") {
      isMonitoring = true;
      meetingId = request.meetingId;

      // Add visual indicator
      const indicator = document.createElement("div");
      indicator.id = "ai-monitor-indicator";
      indicator.style.cssText = `
                position: fixed; top: 10px; right: 10px; z-index: 99999;
                background: rgba(255,0,0,0.8); color: white; padding: 8px 15px;
                border-radius: 20px; font-size: 12px; font-weight: bold;
                animation: pulse 2s infinite;
            `;
      indicator.textContent = "🔴 AI Monitoring Active";
      document.body.appendChild(indicator);

      sendResponse({ status: "monitoring_started" });
    }

    if (request.action === "stop_monitoring") {
      isMonitoring = false;
      const indicator = document.getElementById("ai-monitor-indicator");
      if (indicator) indicator.remove();
      sendResponse({ status: "monitoring_stopped" });
    }
  });

  // Detect Google Meet participants
  function getParticipants() {
    const participants = [];
    const nameElements = document.querySelectorAll("[data-participant-id]");
    nameElements.forEach((el) => {
      participants.push({
        name: el.textContent,
        id: el.getAttribute("data-participant-id"),
      });
    });
    return participants;
  }

  // Detect meeting status
  function checkMeetingStatus() {
    const joinButton = document.querySelector("[data-is-muted]");
    return !!joinButton;
  }

  console.log("🎯 AI Meeting Analyzer extension loaded on Google Meet");
})();
