// chrome_extension/popup.js
const SERVER_URL = "http://localhost:5000";
let currentMeetingId = null;

async function startRecording() {
  const name = document.getElementById("candidate-name").value || "New Meeting";

  try {
    const response = await fetch(`${SERVER_URL}/api/meeting/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: name,
        meeting_type: "interview",
        platform: "google_meet",
      }),
    });

    const data = await response.json();

    if (data.success) {
      currentMeetingId = data.meeting_id;

      // Save to storage
      chrome.storage.local.set({ meetingId: currentMeetingId });

      // Notify content script
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        chrome.tabs.sendMessage(tabs[0].id, {
          action: "start_monitoring",
          meetingId: currentMeetingId,
        });
      });

      // Update UI
      document.getElementById("status").textContent = "🔴 Recording Active";
      document.getElementById("status").className = "status status-active";
      document.getElementById("btn-start").style.display = "none";
      document.getElementById("btn-stop").style.display = "block";
    }
  } catch (error) {
    alert("Error: " + error.message);
  }
}

async function stopRecording() {
  try {
    const response = await fetch(`${SERVER_URL}/api/meeting/stop`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ meeting_id: currentMeetingId }),
    });

    const data = await response.json();

    if (data.success) {
      // Notify content script
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        chrome.tabs.sendMessage(tabs[0].id, {
          action: "stop_monitoring",
        });
      });

      document.getElementById("status").textContent = "✅ Analyzing...";
      document.getElementById("btn-start").style.display = "block";
      document.getElementById("btn-stop").style.display = "none";

      // Open dashboard
      chrome.tabs.create({ url: `${SERVER_URL}/report/${currentMeetingId}` });
    }
  } catch (error) {
    alert("Error: " + error.message);
  }
}

function openDashboard() {
  chrome.tabs.create({ url: `${SERVER_URL}/dashboard` });
}
