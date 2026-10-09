/**
 * Intelligent Personal Health Record (PHR) Assistant
 * Client-Side Application Logic (Vanilla JavaScript)
 * Strictly enforces safe DOM rendering (textContent) and matches verified API contracts.
 */

(function () {
    "use strict";

    // Application State
    let activeSchedules = [];
    let currentAlertingEventId = null;
    let reminderCheckIntervalId = null;

    // Helper: Format Date to YYYY-MM-DD using local time
    function getLocalDateString(dateObj = new Date()) {
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, "0");
        const day = String(dateObj.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    // Helper: Format Time to HH:MM (24-hour) using local time
    function getLocalTimeString(dateObj = new Date()) {
        const hours = String(dateObj.getHours()).padStart(2, "0");
        const minutes = String(dateObj.getMinutes()).padStart(2, "0");
        return `${hours}:${minutes}`;
    }

    // Helper: Safe element text assignment
    function setText(elemOrId, text) {
        const el = typeof elemOrId === "string" ? document.getElementById(elemOrId) : elemOrId;
        if (el) {
            el.textContent = text !== null && text !== undefined ? String(text) : "";
        }
    }

    // =========================================================================
    // 1. Accessible Tab Switching & Navigation
    // =========================================================================
    function initTabs() {
        const tabButtons = Array.from(document.querySelectorAll('.tab-nav button[role="tab"]'));
        const tabPanels = Array.from(document.querySelectorAll('.tab-panel'));

        function switchTab(targetBtn) {
            tabButtons.forEach(btn => {
                const isSelected = btn === targetBtn;
                btn.setAttribute("aria-selected", isSelected ? "true" : "false");
                btn.setAttribute("tabindex", isSelected ? "0" : "-1");
            });

            const targetPanelId = targetBtn.getAttribute("aria-controls");
            tabPanels.forEach(panel => {
                if (panel.id === targetPanelId) {
                    panel.classList.remove("hidden");
                } else {
                    panel.classList.add("hidden");
                }
            });

            // Auto-load data for destination tabs
            if (targetPanelId === "panel-history") {
                loadHealthHistory();
            } else if (targetPanelId === "panel-reminders") {
                loadMedicationSchedules();
            } else if (targetPanelId === "panel-summary") {
                loadHealthSummary();
            }
        }

        tabButtons.forEach((btn, idx) => {
            btn.addEventListener("click", () => switchTab(btn));

            // Keyboard navigation (Arrow keys)
            btn.addEventListener("keydown", (e) => {
                let nextIdx = null;
                if (e.key === "ArrowRight") {
                    nextIdx = (idx + 1) % tabButtons.length;
                } else if (e.key === "ArrowLeft") {
                    nextIdx = (idx - 1 + tabButtons.length) % tabButtons.length;
                } else if (e.key === "Home") {
                    nextIdx = 0;
                } else if (e.key === "End") {
                    nextIdx = tabButtons.length - 1;
                }

                if (nextIdx !== null) {
                    e.preventDefault();
                    tabButtons[nextIdx].focus();
                    switchTab(tabButtons[nextIdx]);
                }
            });
        });

        // Quick-action button from empty history view
        const historyAddBtn = document.getElementById("history-go-add");
        if (historyAddBtn) {
            historyAddBtn.addEventListener("click", () => {
                const recordTabBtn = document.getElementById("tab-btn-record");
                if (recordTabBtn) {
                    recordTabBtn.focus();
                    switchTab(recordTabBtn);
                }
            });
        }
    }

    // =========================================================================
    // 2. Feature 1: Medical Q&A Chatbot
    // =========================================================================
    function initChatbot() {
        const chatForm = document.getElementById("chat-form");
        const chatInput = document.getElementById("chat-input");
        const submitBtn = document.getElementById("chat-submit-btn");
        const resultArea = document.getElementById("chat-result-area");

        if (!chatForm || !chatInput || !submitBtn || !resultArea) return;

        chatForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const question = chatInput.value.trim();
            if (!question) return;

            // Loading state
            submitBtn.disabled = true;
            submitBtn.textContent = "Searching...";

            try {
                const response = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question })
                });

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || "Unable to retrieve medical information.");
                }

                // Render Results
                resultArea.classList.remove("hidden");
                const badge = document.getElementById("chat-status-badge");
                if (data.is_matched) {
                    badge.textContent = "Verified Medical Match";
                    badge.className = "badge badge-matched";
                    setText("chat-score-text", `Cosine Similarity: ${Number(data.score).toFixed(4)} (Threshold: ${data.threshold})`);
                } else {
                    badge.textContent = "Low-Confidence Fallback";
                    badge.className = "badge badge-fallback";
                    setText("chat-score-text", `Confidence: ${Number(data.score).toFixed(4)} (Below Threshold: ${data.threshold})`);
                }

                setText("chat-query-echo", `Query: "${data.query}"`);
                setText("chat-focus", data.focus || "General Topic");
                setText("chat-source", data.source || "NIH Public Repository");
                setText("chat-qtype", data.qtype || "General Question");
                setText("chat-matched-q", data.matched_question || "N/A (No sufficiently close question match)");
                setText("chat-answer-text", data.answer || "No response provided.");

                // Link handling
                const linkContainer = document.getElementById("chat-link-container");
                const sourceUrl = document.getElementById("chat-source-url");
                if (data.url && data.is_matched) {
                    sourceUrl.href = data.url;
                    sourceUrl.textContent = data.url;
                    linkContainer.classList.remove("hidden");
                } else {
                    linkContainer.classList.add("hidden");
                }

                setText("chat-disclaimer", data.disclaimer || "");

            } catch (err) {
                alert(`Error: ${err.message}`);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "Search";
            }
        });
    }

    // =========================================================================
    // 3. Feature 2: Save Personal Health Records
    // =========================================================================
    function initRecordEntry() {
        const recordForm = document.getElementById("record-form");
        const typeSelect = document.getElementById("record-type");
        const dateInput = document.getElementById("record-date");
        const measurementFields = document.getElementById("measurement-fields");
        const feedback = document.getElementById("record-feedback");
        const submitBtn = document.getElementById("record-submit-btn");

        if (!recordForm || !typeSelect || !dateInput) return;

        // Default to today's date
        dateInput.value = getLocalDateString();

        // Toggle measurement fields based on category
        function toggleMeasurementFields() {
            if (typeSelect.value === "measurement") {
                measurementFields.classList.remove("hidden");
            } else {
                measurementFields.classList.add("hidden");
                document.getElementById("metric-name").value = "";
                document.getElementById("metric-value").value = "";
                document.getElementById("metric-unit").value = "";
            }
        }
        typeSelect.addEventListener("change", toggleMeasurementFields);
        toggleMeasurementFields();

        // Handle Form Submission
        recordForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            feedback.className = "feedback-banner hidden";
            feedback.textContent = "";

            const recordType = typeSelect.value;
            const title = document.getElementById("record-title").value.trim();
            const recordedDate = dateInput.value;
            const description = document.getElementById("record-description").value.trim();

            const payload = {
                record_type: recordType,
                title: title,
                recorded_date: recordedDate,
                description: description || null
            };

            if (recordType === "measurement") {
                const metricName = document.getElementById("metric-name").value.trim();
                const metricValue = document.getElementById("metric-value").value.trim();
                const metricUnit = document.getElementById("metric-unit").value.trim();

                payload.metric_name = metricName || null;
                payload.metric_value = metricValue !== "" ? parseFloat(metricValue) : null;
                payload.metric_unit = metricUnit || null;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = "Saving...";

            try {
                const response = await fetch("/api/records", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || "Failed to save health record.");
                }

                feedback.className = "feedback-banner feedback-success";
                feedback.textContent = `Success: Health record "${data.record.title}" was saved to local SQLite database.`;

                // Reset inputs while preserving today's date
                recordForm.reset();
                dateInput.value = getLocalDateString();
                toggleMeasurementFields();

            } catch (err) {
                feedback.className = "feedback-banner feedback-error";
                feedback.textContent = `Error: ${err.message}`;
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "Save Health Record";
            }
        });
    }

    // =========================================================================
    // 4. Feature 3: Chronological Health History
    // =========================================================================
    async function loadHealthHistory(filterType = "") {
        const container = document.getElementById("history-list");
        const loading = document.getElementById("history-loading");
        const emptyState = document.getElementById("history-empty");

        if (!container || !loading || !emptyState) return;

        loading.classList.remove("hidden");
        emptyState.classList.add("hidden");
        container.textContent = ""; // Clear existing cards safely

        try {
            const url = filterType ? `/api/records?type=${encodeURIComponent(filterType)}` : "/api/records";
            const response = await fetch(url);
            const data = await response.json();

            loading.classList.add("hidden");

            if (!response.ok) {
                throw new Error(data.error || "Unable to load health history.");
            }

            if (!data.records || data.records.length === 0) {
                emptyState.classList.remove("hidden");
                return;
            }

            // Build chronological cards using safe DOM methods
            data.records.forEach((rec) => {
                const card = document.createElement("article");
                card.className = "timeline-card";

                const header = document.createElement("div");
                header.className = "timeline-card-header";

                const titleEl = document.createElement("h3");
                titleEl.className = "timeline-title";
                titleEl.textContent = rec.title;

                const dateEl = document.createElement("span");
                dateEl.className = "timeline-date";
                dateEl.textContent = rec.recorded_date;

                header.appendChild(titleEl);
                header.appendChild(dateEl);
                card.appendChild(header);

                // Category badge
                const badge = document.createElement("span");
                badge.className = `badge badge-${rec.record_type}`;
                const typeLabels = {
                    symptom: "Symptom",
                    measurement: "Measurement",
                    general_note: "General Note"
                };
                badge.textContent = typeLabels[rec.record_type] || rec.record_type;
                card.appendChild(badge);

                // Metric detail if present
                if (rec.metric_name && rec.metric_value !== null) {
                    const metricBadge = document.createElement("div");
                    metricBadge.className = "timeline-metric-badge";
                    metricBadge.textContent = `${rec.metric_name}: ${rec.metric_value} ${rec.metric_unit || ""}`.trim();
                    card.appendChild(metricBadge);
                }

                // Description
                if (rec.description) {
                    const descEl = document.createElement("p");
                    descEl.className = "timeline-desc";
                    descEl.textContent = rec.description;
                    card.appendChild(descEl);
                }

                container.appendChild(card);
            });

        } catch (err) {
            loading.classList.add("hidden");
            const errP = document.createElement("p");
            errP.className = "feedback-banner feedback-error";
            errP.textContent = `Error loading history: ${err.message}`;
            container.appendChild(errP);
        }
    }

    function initHistory() {
        const filterSelect = document.getElementById("history-filter");
        if (filterSelect) {
            filterSelect.addEventListener("change", () => {
                loadHealthHistory(filterSelect.value);
            });
        }
    }

    // =========================================================================
    // 5. Feature 4: Medication Reminders & Schedules
    // =========================================================================
    async function loadMedicationSchedules() {
        const listContainer = document.getElementById("med-list");
        const loading = document.getElementById("med-loading");
        const emptyState = document.getElementById("med-empty");
        const badge = document.getElementById("med-count-badge");

        if (!listContainer || !loading || !emptyState) return;

        loading.classList.remove("hidden");
        emptyState.classList.add("hidden");

        // Clear existing items while preserving loading/empty elements
        const items = listContainer.querySelectorAll(".schedule-item");
        items.forEach(el => el.remove());

        try {
            const response = await fetch("/api/medications");
            const data = await response.json();
            loading.classList.add("hidden");

            if (!response.ok) {
                throw new Error(data.error || "Unable to load medication schedules.");
            }

            activeSchedules = data.schedules || [];
            if (badge) {
                badge.textContent = `${activeSchedules.length} Active`;
            }

            if (activeSchedules.length === 0) {
                emptyState.classList.remove("hidden");
                return;
            }

            // Render schedule rows safely
            activeSchedules.forEach((sched) => {
                const item = document.createElement("div");
                item.className = "schedule-item";

                const info = document.createElement("div");
                info.className = "schedule-info";

                const nameEl = document.createElement("h4");
                nameEl.textContent = `${sched.medication_name} (${sched.dosage})`;

                const metaEl = document.createElement("p");
                metaEl.className = "schedule-meta";
                metaEl.textContent = `Frequency: ${sched.frequency} | Started: ${sched.start_date}`;

                const timeBadge = document.createElement("span");
                timeBadge.className = "schedule-time-badge";
                timeBadge.textContent = `Reminder: ${sched.reminder_time} (24h)`;

                info.appendChild(nameEl);
                info.appendChild(metaEl);
                info.appendChild(timeBadge);

                if (sched.instructions) {
                    const instEl = document.createElement("p");
                    instEl.className = "schedule-meta";
                    instEl.style.fontStyle = "italic";
                    instEl.textContent = `Instructions: ${sched.instructions}`;
                    info.appendChild(instEl);
                }

                // Deactivate button (no deletion)
                const deactBtn = document.createElement("button");
                deactBtn.type = "button";
                deactBtn.className = "btn btn-sm btn-secondary";
                deactBtn.textContent = "Deactivate";
                deactBtn.addEventListener("click", async () => {
                    if (confirm(`Deactivate reminders for ${sched.medication_name}?`)) {
                        deactBtn.disabled = true;
                        try {
                            const res = await fetch(`/api/medications/${sched.id}/deactivate`, { method: "POST" });
                            if (!res.ok) throw new Error("Deactivation failed.");
                            loadMedicationSchedules();
                        } catch (err) {
                            alert(err.message);
                            deactBtn.disabled = false;
                        }
                    }
                });

                item.appendChild(info);
                item.appendChild(deactBtn);
                listContainer.appendChild(item);
            });

        } catch (err) {
            loading.classList.add("hidden");
            const errP = document.createElement("p");
            errP.className = "feedback-banner feedback-error";
            errP.textContent = `Error: ${err.message}`;
            listContainer.appendChild(errP);
        }
    }

    // In-Browser Periodic Reminder Trigger Check (Every 30 seconds)
    async function checkDueReminders() {
        if (!activeSchedules || activeSchedules.length === 0) return;

        const todayStr = getLocalDateString();
        const nowTimeStr = getLocalTimeString();

        for (const sched of activeSchedules) {
            // Check if schedule is active for today and matches current 24h minute
            if (sched.start_date <= todayStr && sched.reminder_time === nowTimeStr) {
                try {
                    // Call duplicate-safe occurrence logging
                    const response = await fetch("/api/reminders/log", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            medication_id: sched.id,
                            scheduled_date: todayStr,
                            scheduled_time: nowTimeStr
                        })
                    });

                    const data = await response.json();

                    // If successfully logged as a NEW occurrence (HTTP 201), trigger the in-app alert!
                    if (response.status === 201 && data.status === "logged") {
                        triggerInAppAlert(data.event, sched);
                    }
                    // If already logged earlier today (HTTP 200), skip without duplicate alert

                } catch (err) {
                    console.error("Reminder check failed for schedule:", sched.id, err);
                }
            }
        }
    }

    // Show In-App Banner Alert
    function triggerInAppAlert(eventData, scheduleData) {
        currentAlertingEventId = eventData.id;
        const banner = document.getElementById("alert-banner");
        const msgEl = document.getElementById("alert-message");

        if (banner && msgEl) {
            msgEl.textContent = `Medication Reminder: Time for ${scheduleData.medication_name} (${scheduleData.dosage}) - Scheduled for ${scheduleData.reminder_time}.`;
            banner.classList.remove("hidden");
        }
    }

    function initReminders() {
        const medForm = document.getElementById("medication-form");
        const startDateInput = document.getElementById("med-start-date");
        const feedback = document.getElementById("med-feedback");
        const submitBtn = document.getElementById("med-submit-btn");

        if (!medForm || !startDateInput) return;

        // Auto-fill today's date
        startDateInput.value = getLocalDateString();

        medForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            feedback.className = "feedback-banner hidden";
            feedback.textContent = "";

            const payload = {
                medication_name: document.getElementById("med-name").value.trim(),
                dosage: document.getElementById("med-dosage").value.trim(),
                frequency: document.getElementById("med-frequency").value.trim(),
                reminder_time: document.getElementById("med-time").value.trim(),
                start_date: startDateInput.value,
                instructions: document.getElementById("med-instructions").value.trim() || null
            };

            submitBtn.disabled = true;
            submitBtn.textContent = "Adding...";

            try {
                const response = await fetch("/api/medications", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || "Failed to create medication schedule.");
                }

                feedback.className = "feedback-banner feedback-success";
                feedback.textContent = `Success: Medication routine "${data.medication.medication_name}" created.`;

                medForm.reset();
                startDateInput.value = getLocalDateString();
                loadMedicationSchedules();

            } catch (err) {
                feedback.className = "feedback-banner feedback-error";
                feedback.textContent = `Error: ${err.message}`;
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "Add Schedule";
            }
        });

        // Banner Acknowledge Button
        const ackBtn = document.getElementById("alert-ack-btn");
        if (ackBtn) {
            ackBtn.addEventListener("click", async () => {
                if (!currentAlertingEventId) return;
                try {
                    const response = await fetch("/api/reminders/acknowledge", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ event_id: currentAlertingEventId })
                    });
                    if (response.ok) {
                        const banner = document.getElementById("alert-banner");
                        if (banner) banner.classList.add("hidden");
                        currentAlertingEventId = null;
                    }
                } catch (err) {
                    console.error("Acknowledgment failed:", err);
                }
            });
        }

        // Banner Dismiss Button
        const dismissBtn = document.getElementById("alert-dismiss-btn");
        if (dismissBtn) {
            dismissBtn.addEventListener("click", () => {
                const banner = document.getElementById("alert-banner");
                if (banner) banner.classList.add("hidden");
            });
        }

        // Start Periodic Timer (every 30 seconds)
        if (!reminderCheckIntervalId) {
            reminderCheckIntervalId = setInterval(checkDueReminders, 30000);
        }
    }

    // =========================================================================
    // 6. Feature 5: Factual Health Record Summary
    // =========================================================================
    async function loadHealthSummary() {
        const loading = document.getElementById("summary-loading");
        const emptyView = document.getElementById("summary-empty-view");
        const activeView = document.getElementById("summary-active-view");

        if (!loading || !emptyView || !activeView) return;

        loading.classList.remove("hidden");
        emptyView.classList.add("hidden");
        activeView.classList.add("hidden");

        try {
            const response = await fetch("/api/summary");
            const data = await response.json();
            loading.classList.add("hidden");

            if (!response.ok) {
                throw new Error(data.error || "Unable to compute health summary.");
            }

            if (data.status === "empty") {
                emptyView.classList.remove("hidden");
                setText("summary-empty-msg", data.message || "No health records have been logged yet.");
                return;
            }

            // Populate Factual Dashboard
            activeView.classList.remove("hidden");
            setText("sum-total-records", data.total_records);
            setText("sum-symptoms-count", data.records_by_type?.symptom || 0);
            setText("sum-measurements-count", data.records_by_type?.measurement || 0);
            setText("sum-notes-count", data.records_by_type?.general_note || 0);
            setText("sum-timespan", data.date_span?.span_description || "N/A");

            // Documented Symptoms tags
            const symptomsList = document.getElementById("sum-symptoms-list");
            symptomsList.textContent = "";
            if (data.symptoms && data.symptoms.length > 0) {
                data.symptoms.forEach(s => {
                    const tag = document.createElement("span");
                    tag.className = "tag-item";
                    tag.textContent = `${s.symptom} (${s.frequency}x)`;
                    symptomsList.appendChild(tag);
                });
            } else {
                const noSymP = document.createElement("p");
                noSymP.className = "meta-text";
                noSymP.textContent = "No symptoms recorded in current logs.";
                symptomsList.appendChild(noSymP);
            }

            // Health Measurements Breakdown
            const measurementsGrid = document.getElementById("sum-measurements-container");
            measurementsGrid.textContent = "";
            if (data.measurements && data.measurements.length > 0) {
                data.measurements.forEach(m => {
                    const mCard = document.createElement("div");
                    mCard.className = "metric-summary-card";

                    const h5 = document.createElement("h5");
                    h5.textContent = m.metric_name;

                    const latestP = document.createElement("p");
                    latestP.className = "latest-val";
                    latestP.textContent = `Latest: ${m.latest_value} ${m.unit || ""}`.trim();

                    const dateP = document.createElement("p");
                    dateP.className = "meta-text";
                    dateP.textContent = `Recorded: ${m.latest_recorded_date}`;

                    const noteP = document.createElement("p");
                    noteP.className = "trend-note";
                    noteP.textContent = m.trend_note;

                    mCard.appendChild(h5);
                    mCard.appendChild(latestP);
                    mCard.appendChild(dateP);
                    mCard.appendChild(noteP);
                    measurementsGrid.appendChild(mCard);
                });
            } else {
                const noMeasP = document.createElement("p");
                noMeasP.className = "meta-text";
                noMeasP.textContent = "No numeric measurements recorded in current logs.";
                measurementsGrid.appendChild(noMeasP);
            }

            setText("summary-disclaimer-text", data.disclaimer || "");

        } catch (err) {
            loading.classList.add("hidden");
            alert(`Error: ${err.message}`);
        }
    }

    function initSummary() {
        const refreshBtn = document.getElementById("summary-refresh-btn");
        if (refreshBtn) {
            refreshBtn.addEventListener("click", loadHealthSummary);
        }
    }

    // =========================================================================
    // Initialization on DOM Ready
    // =========================================================================
    document.addEventListener("DOMContentLoaded", () => {
        initTabs();
        initChatbot();
        initRecordEntry();
        initHistory();
        initReminders();
        initSummary();
        // Initial load of active schedules for background reminder checks
        loadMedicationSchedules();
    });

})();

