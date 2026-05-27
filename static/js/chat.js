(function () {
    const pageDataNode = document.getElementById("chat-page-data");
    const messagesNode = document.getElementById("initial-messages");
    const form = document.getElementById("message-form");
    const list = document.getElementById("message-list");

    if (!pageDataNode || !messagesNode || !form || !list) {
        return;
    }

    const pageData = JSON.parse(pageDataNode.textContent);
    const initialMessages = JSON.parse(messagesNode.textContent);
    const contentInput = form.querySelector('[name="content"]');
    const imageInput = form.querySelector('input[name="image"]');
    const voiceInput = form.querySelector('input[name="voice_note"]');
    const attachmentStatus = document.getElementById("attachment-status");
    const imagePreview = document.getElementById("image-preview");
    const imagePreviewShell = document.getElementById("image-preview-shell");
    const imageClear = document.getElementById("image-clear");
    const voicePreview = document.getElementById("voice-preview");
    const voicePreviewShell = document.getElementById("voice-preview-shell");
    const recordingIndicator = document.getElementById("recording-indicator");
    const recordingTimer = document.getElementById("recording-timer");
    const recordingStateText = document.getElementById("recording-state-text");
    const recordStart = document.getElementById("record-start");
    const recordStop = document.getElementById("record-stop");
    const recordClear = document.getElementById("record-clear");
    const emojiToggle = document.getElementById("emoji-toggle");
    const emojiMenu = document.getElementById("emoji-menu");
    const emojiButtons = Array.from(form.querySelectorAll("[data-insert-emoji]"));
    const supportedReactions = [
        { emoji: "👍", label: "Lubię" },
        { emoji: "👎", label: "Nie lubię" },
        { emoji: "❤️", label: "Serce" },
    ];
    let recorder = null;
    let recordedChunks = [];
    let recordingStream = null;
    let imagePreviewUrl = "";
    let voicePreviewUrl = "";
    let recordingStartedAt = null;
    let recordingTimerId = null;

    function toast(title, body) {
        if (typeof window.discordToast === "function") {
            window.discordToast(title, body);
        }
    }

    function getCsrfToken() {
        const tokenInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
        return tokenInput ? tokenInput.value : "";
    }

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value;
        return div.innerHTML;
    }

    function canEditMessage(message) {
        if (message.is_deleted) {
            return false;
        }
        if (message.author.id === pageData.viewerId) {
            return true;
        }
        return pageData.viewerCanModerateMessages && pageData.chatType !== "direct";
    }

    function canDeleteMessage(message) {
        if (message.is_deleted) {
            return false;
        }
        if (message.author.id === pageData.viewerId) {
            return true;
        }
        return pageData.viewerCanModerateMessages && pageData.chatType !== "direct";
    }

    function getReactionBucket(message, emoji) {
        return (message.reactions || []).find((item) => item.emoji === emoji) || null;
    }

    function renderReactionButtons(message) {
        if (message.is_deleted) {
            return "";
        }

        const buttons = supportedReactions.map((reaction) => {
            const bucket = getReactionBucket(message, reaction.emoji);
            const count = bucket ? bucket.count : 0;
            const isActive = bucket ? bucket.reactor_ids.includes(pageData.viewerId) : false;
            const tooltipText = bucket && bucket.reactor_names.length
                ? bucket.reactor_names.join(", ")
                : `Dodaj reakcję ${reaction.label.toLowerCase()}`;
            return `
                <button
                    type="button"
                    class="reaction-chip ${isActive ? "is-active" : ""}"
                    data-action="react"
                    data-url="${message.reaction_url}"
                    data-id="${message.id}"
                    data-emoji="${reaction.emoji}"
                    aria-label="${reaction.label}"
                    title="${escapeHtml(tooltipText)}"
                >
                    <span class="reaction-chip__emoji">${reaction.emoji}</span>
                    ${count ? `<span class="reaction-chip__count">${count}</span>` : ""}
                </button>
            `;
        });

        return `<div class="message-reactions">${buttons.join("")}</div>`;
    }

    function renderMessage(message) {
        const avatar = message.author.avatar_url
            ? `<img src="${message.author.avatar_url}" alt="${escapeHtml(message.author.username)}">`
            : `<span>${escapeHtml(message.author.username.charAt(0).toUpperCase())}</span>`;

        const attachments = [];
        if (message.image_url) {
            attachments.push(
                `<div class="message-attachment"><img src="${message.image_url}" alt="Załączony obraz"></div>`
            );
        }
        if (message.voice_url) {
            attachments.push(
                `<div class="message-attachment"><audio controls class="w-100"><source src="${message.voice_url}"></audio></div>`
            );
        }

        const actionButtons = [];
        if (canEditMessage(message)) {
            actionButtons.push(
                `<button type="button" class="btn btn-sm btn-accent-outline message-action-btn" data-action="edit" data-url="${message.edit_url}" data-id="${message.id}"><i class="bi bi-pencil-square me-1"></i>Edytuj</button>`
            );
        }
        if (canDeleteMessage(message)) {
            actionButtons.push(
                `<button type="button" class="btn btn-sm btn-chat-danger message-action-btn" data-action="delete" data-url="${message.delete_url}" data-id="${message.id}"><i class="bi bi-trash3 me-1"></i>Usuń</button>`
            );
        }

        return `
            <article class="message-card ${message.is_deleted ? "is-deleted" : ""}" data-message-id="${message.id}">
                <div class="avatar-badge ${message.author.status === "online" ? "is-online" : "is-offline"}">${avatar}</div>
                <div>
                    <div class="message-meta">
                        <span class="message-author">${escapeHtml(message.author.username)}</span>
                        <span class="message-role">${escapeHtml(message.author.role)}</span>
                        <span class="message-time">${message.created_at}</span>
                        ${message.edited_at ? `<span class="message-edited">edytowano ${message.edited_at}</span>` : ""}
                    </div>
                    <div class="message-body">${escapeHtml(message.content || "")}</div>
                    ${attachments.join("")}
                    ${renderReactionButtons(message)}
                    ${actionButtons.length ? `<div class="message-actions">${actionButtons.join("")}</div>` : ""}
                </div>
            </article>
        `;
    }

    function upsertMessage(message) {
        const existing = list.querySelector(`[data-message-id="${message.id}"]`);
        if (existing) {
            existing.outerHTML = renderMessage(message);
        } else {
            list.insertAdjacentHTML("beforeend", renderMessage(message));
        }
        list.scrollTop = list.scrollHeight;
    }

    function renderInitialMessages() {
        if (!initialMessages.length) {
            list.innerHTML =
                '<div class="empty-shell">Brak wiadomości. Zacznij rozmowę jako pierwsza osoba w tym kanale.</div>';
            return;
        }
        list.innerHTML = initialMessages.map(renderMessage).join("");
        list.scrollTop = list.scrollHeight;
    }

    function updateAttachmentStatus() {
        const imageName = imageInput.files[0] ? imageInput.files[0].name : "";
        const audioName = voiceInput.files[0] ? voiceInput.files[0].name : "";
        if (imageName && audioName) {
            attachmentStatus.textContent = `${imageName} • ${audioName} - załączniki są gotowe do wysłania.`;
            return;
        }
        if (audioName) {
            attachmentStatus.textContent = `${audioName} - możesz wysłać albo usunąć przed publikacją.`;
            return;
        }
        if (imageName) {
            attachmentStatus.textContent = `${imageName} - możesz wysłać albo usunąć przed publikacją.`;
            return;
        }
        attachmentStatus.textContent = "Możesz wysłać tekst, obraz lub nagranie głosowe.";
    }

    function insertEmojiIntoMessage(emoji) {
        if (!contentInput) {
            return;
        }

        const start = contentInput.selectionStart ?? contentInput.value.length;
        const end = contentInput.selectionEnd ?? contentInput.value.length;
        const before = contentInput.value.slice(0, start);
        const after = contentInput.value.slice(end);
        const leadingSpace = before.length > 0 && !/\s$/.test(before) ? " " : "";
        const trailingSpace = after.length > 0 && !/^\s/.test(after) ? " " : "";
        const insertion = `${leadingSpace}${emoji}${trailingSpace}`;

        contentInput.value = `${before}${insertion}${after}`;
        const caretPosition = before.length + insertion.length;
        contentInput.focus();
        contentInput.setSelectionRange(caretPosition, caretPosition);
        contentInput.dispatchEvent(new Event("input", { bubbles: true }));
    }

    function closeEmojiMenu() {
        if (!emojiMenu || !emojiToggle) {
            return;
        }
        emojiMenu.classList.add("d-none");
        emojiToggle.setAttribute("aria-expanded", "false");
    }

    function toggleEmojiMenu() {
        if (!emojiMenu || !emojiToggle) {
            return;
        }
        const shouldOpen = emojiMenu.classList.contains("d-none");
        emojiMenu.classList.toggle("d-none", !shouldOpen);
        emojiToggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    }

    function formatDuration(totalSeconds) {
        const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
        const seconds = String(totalSeconds % 60).padStart(2, "0");
        return `${minutes}:${seconds}`;
    }

    function stopRecordingIndicator() {
        if (recordingTimerId) {
            window.clearInterval(recordingTimerId);
            recordingTimerId = null;
        }
        recordingStartedAt = null;
        if (recordingIndicator) {
            recordingIndicator.classList.add("d-none");
            recordingIndicator.classList.remove("is-processing");
        }
        if (recordingTimer) {
            recordingTimer.textContent = "00:00";
        }
        if (recordingStateText) {
            recordingStateText.textContent = "Nagrywanie w toku";
        }
    }

    function startRecordingIndicator() {
        stopRecordingIndicator();
        recordingStartedAt = Date.now();
        if (recordingIndicator) {
            recordingIndicator.classList.remove("d-none");
            recordingIndicator.classList.remove("is-processing");
        }
        if (recordingTimer) {
            recordingTimer.textContent = "00:00";
        }
        if (recordingStateText) {
            recordingStateText.textContent = "Nagrywanie w toku";
        }
        recordingTimerId = window.setInterval(() => {
            if (!recordingStartedAt || !recordingTimer) {
                return;
            }
            const seconds = Math.max(
                0,
                Math.floor((Date.now() - recordingStartedAt) / 1000)
            );
            recordingTimer.textContent = formatDuration(seconds);
        }, 1000);
    }

    function setRecordingProcessingState() {
        if (!recordingIndicator) {
            return;
        }
        recordingIndicator.classList.remove("d-none");
        recordingIndicator.classList.add("is-processing");
        if (recordingStateText) {
            recordingStateText.textContent = "Zapisywanie nagrania...";
        }
    }

    function readResponseText(text) {
        if (!text) {
            return "";
        }
        const doc = new DOMParser().parseFromString(text, "text/html");
        const raw = (doc.body && doc.body.textContent) || text;
        return raw.replace(/\s+/g, " ").trim().slice(0, 220);
    }

    async function readResponsePayload(response) {
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            return { json: null, text: await response.text() };
        }
        return { json: await response.json(), text: "" };
    }

    function firstFieldError(payload) {
        if (!payload || !payload.errors) {
            return "";
        }

        for (const value of Object.values(payload.errors)) {
            if (!Array.isArray(value) || !value.length) {
                continue;
            }
            const first = value[0];
            if (typeof first === "string") {
                return first;
            }
            if (first && typeof first.message === "string") {
                return first.message;
            }
        }
        return "";
    }

    function describeError(response, payload, text, fallback) {
        const statusLabel = response ? `HTTP ${response.status}` : "";
        const message = payload ? payload.error || firstFieldError(payload) : "";
        if (message) {
            return statusLabel ? `${statusLabel}: ${message}` : message;
        }
        const snippet = readResponseText(text);
        if (snippet) {
            return statusLabel ? `${statusLabel}: ${snippet}` : snippet;
        }
        return statusLabel ? `${statusLabel}: ${fallback}` : fallback;
    }

    function clearImagePreviewUrl() {
        if (!imagePreviewUrl) {
            return;
        }
        URL.revokeObjectURL(imagePreviewUrl);
        imagePreviewUrl = "";
    }

    function hideImagePreview() {
        clearImagePreviewUrl();
        if (imagePreview) {
            imagePreview.removeAttribute("src");
        }
        if (imagePreviewShell) {
            imagePreviewShell.classList.add("d-none");
        }
    }

    function setImagePreview(file) {
        clearImagePreviewUrl();
        imagePreviewUrl = URL.createObjectURL(file);
        if (imagePreview) {
            imagePreview.src = imagePreviewUrl;
        }
        if (imagePreviewShell) {
            imagePreviewShell.classList.remove("d-none");
        }
    }

    function clearImageSelection() {
        const transfer = new DataTransfer();
        imageInput.files = transfer.files;
        hideImagePreview();
        updateAttachmentStatus();
    }

    function clearVoicePreviewUrl() {
        if (!voicePreviewUrl) {
            return;
        }
        URL.revokeObjectURL(voicePreviewUrl);
        voicePreviewUrl = "";
    }

    function stopRecordingStream() {
        if (!recordingStream) {
            return;
        }
        recordingStream.getTracks().forEach((track) => track.stop());
        recordingStream = null;
    }

    function hideVoicePreview() {
        clearVoicePreviewUrl();
        voicePreview.pause();
        voicePreview.removeAttribute("src");
        voicePreview.load();
        if (voicePreviewShell) {
            voicePreviewShell.classList.add("d-none");
        }
        if (recordClear) {
            recordClear.classList.add("d-none");
            recordClear.disabled = false;
        }
    }

    function setVoicePreview(file) {
        clearVoicePreviewUrl();
        voicePreviewUrl = URL.createObjectURL(file);
        voicePreview.src = voicePreviewUrl;
        if (voicePreviewShell) {
            voicePreviewShell.classList.remove("d-none");
        }
        if (recordClear) {
            recordClear.classList.remove("d-none");
            recordClear.disabled = false;
        }
    }

    function clearVoiceSelection() {
        const transfer = new DataTransfer();
        voiceInput.files = transfer.files;
        recordedChunks = [];
        stopRecordingIndicator();
        hideVoicePreview();
        stopRecordingStream();
        updateAttachmentStatus();
    }

    async function sendMessage(event) {
        event.preventDefault();
        const formData = new FormData(form);
        try {
            const response = await fetch(pageData.postUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: formData,
            });
            const { json: payload, text } = await readResponsePayload(response);
            if (!response.ok) {
                console.error("Send message failed", response.status, text || payload);
                toast(
                    "Błąd",
                    describeError(response, payload, text, "Nie udało się wysłać wiadomości.")
                );
                return;
            }
            if (!payload) {
                toast("Błąd", "Serwer zwrócił nieoczekiwaną odpowiedź.");
                return;
            }

            if (list.querySelector(".empty-shell")) {
                list.innerHTML = "";
            }
            upsertMessage(payload.message);
            form.reset();
            clearImageSelection();
            clearVoiceSelection();
            updateAttachmentStatus();
        } catch (error) {
            toast("Błąd", "Nie udało się połączyć z serwerem.");
        }
    }

    async function postSimple(url, body) {
        const params = new URLSearchParams();
        Object.entries(body).forEach(([key, value]) => params.append(key, value));
        params.append("_action", "1");

        try {
            const response = await fetch(url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: params.toString(),
            });
            const { json: payload, text } = await readResponsePayload(response);
            if (!response.ok) {
                console.error("Chat action failed", url, response.status, text || payload);
                toast("Błąd", describeError(response, payload, text, "Akcja nie powiodła się."));
                return null;
            }
            if (!payload) {
                toast("Błąd", "Serwer zwrócił nieoczekiwaną odpowiedź.");
                return null;
            }
            return payload.message;
        } catch (error) {
            toast("Błąd", "Nie udało się połączyć z serwerem.");
            return null;
        }
    }

    async function markConversationRead() {
        if (!pageData.readUrl || document.hidden) {
            return;
        }

        try {
            await fetch(pageData.readUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: "_read=1",
            });
            if (typeof window.discordRefreshUiState === "function") {
                window.discordRefreshUiState();
            }
        } catch (error) {
            console.debug("Mark read skipped", error);
        }
    }

    async function handleListClick(event) {
        const target = event.target.closest("[data-action]");
        if (!target) {
            return;
        }

        const action = target.dataset.action;
        const url = target.dataset.url;

        if (action === "edit") {
            const card = target.closest(".message-card");
            const body = card ? card.querySelector(".message-body") : null;
            const nextContent = window.prompt(
                "Edytuj wiadomość",
                body ? body.textContent.trim() : ""
            );
            if (nextContent === null) {
                return;
            }
            const message = await postSimple(url, { content: nextContent });
            if (message) {
                upsertMessage(message);
            }
            return;
        }

        if (action === "delete") {
            if (!window.confirm("Usunąć tę wiadomość?")) {
                return;
            }
            const message = await postSimple(url, {});
            if (message) {
                upsertMessage(message);
            }
            return;
        }

        if (action === "react") {
            const emoji = target.dataset.emoji || "👍";
            const message = await postSimple(url, { emoji });
            if (message) {
                upsertMessage(message);
            }
        }
    }

    function connectWebSocket() {
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        const socket = new WebSocket(
            `${scheme}://${window.location.host}${pageData.websocketPath}`
        );

        socket.addEventListener("message", (event) => {
            const data = JSON.parse(event.data);
            if (!data.payload) {
                return;
            }
            if (data.event === "membership_revoked" || data.event === "channel_banned") {
                if (data.payload.targetUserId === pageData.viewerId) {
                    const actionText =
                        data.event === "channel_banned"
                            ? "zablokował(a) Cię na kanale"
                            : "usunął(ęła) Cię z kanału";
                    toast(
                        "Kanał",
                        `${data.payload.actorName} ${actionText} ${data.payload.channelName}.`
                    );
                    window.location.href = data.payload.redirectUrl || "/";
                }
                return;
            }
            if (!["message_created", "message_updated", "message_deleted"].includes(data.event)) {
                return;
            }
            if (list.querySelector(".empty-shell")) {
                list.innerHTML = "";
            }
            upsertMessage(data.payload);

            if (data.event === "message_created" && data.payload.author.id !== pageData.viewerId) {
                if (!document.hidden) {
                    markConversationRead();
                }
                toast(
                    `Nowa wiadomość od ${data.payload.author.username}`,
                    data.payload.content || "Załączono plik."
                );
                if (document.hidden && "Notification" in window && Notification.permission === "granted") {
                    new Notification(`DiscordV2 - ${data.payload.author.username}`, {
                        body: data.payload.content || "Załączono plik.",
                    });
                }
            }
        });

        socket.addEventListener("close", () => {
            window.setTimeout(connectWebSocket, 2000);
        });
    }

    async function startRecording() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            toast("Mikrofon", "Przeglądarka nie obsługuje nagrywania audio.");
            return;
        }

        try {
            clearVoiceSelection();
            recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            recorder = new MediaRecorder(recordingStream);
            recordedChunks = [];
            startRecordingIndicator();

            recorder.addEventListener("dataavailable", (event) => {
                if (event.data.size > 0) {
                    recordedChunks.push(event.data);
                }
            });

            recorder.addEventListener("stop", () => {
                const blob = new Blob(recordedChunks, { type: "audio/webm" });
                const file = new File([blob], `voice-${Date.now()}.webm`, {
                    type: "audio/webm",
                });
                const transfer = new DataTransfer();
                transfer.items.add(file);
                voiceInput.files = transfer.files;
                setVoicePreview(file);
                stopRecordingIndicator();
                updateAttachmentStatus();
                stopRecordingStream();
                recordStart.disabled = false;
                recordStop.disabled = true;
            });

            recorder.start();
            recordStart.disabled = true;
            recordStop.disabled = false;
            if (recordClear) {
                recordClear.disabled = true;
                recordClear.classList.add("d-none");
            }
            attachmentStatus.textContent = "Nagrywanie w toku...";
        } catch (error) {
            toast("Mikrofon", "Nie udało się rozpocząć nagrania.");
            stopRecordingIndicator();
            stopRecordingStream();
        }
    }

    function stopRecording() {
        if (recorder && recorder.state !== "inactive") {
            setRecordingProcessingState();
            recorder.stop();
        }
    }

    function handleVoiceInputChange() {
        const file = voiceInput.files[0];
        if (!file) {
            hideVoicePreview();
            updateAttachmentStatus();
            return;
        }
        setVoicePreview(file);
        updateAttachmentStatus();
    }

    function handleImageInputChange() {
        const file = imageInput.files[0];
        if (!file) {
            hideImagePreview();
            updateAttachmentStatus();
            return;
        }
        setImagePreview(file);
        updateAttachmentStatus();
    }

    renderInitialMessages();
    if (!document.hidden) {
        markConversationRead();
    }
    connectWebSocket();
    form.addEventListener("submit", sendMessage);
    list.addEventListener("click", handleListClick);
    imageInput.addEventListener("change", handleImageInputChange);
    voiceInput.addEventListener("change", handleVoiceInputChange);

    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission().catch(() => {});
    }

    if (recordStart && recordStop) {
        recordStart.addEventListener("click", startRecording);
        recordStop.addEventListener("click", stopRecording);
    }
    if (recordClear) {
        recordClear.addEventListener("click", clearVoiceSelection);
    }
    if (imageClear) {
        imageClear.addEventListener("click", clearImageSelection);
    }
    if (emojiToggle) {
        emojiToggle.addEventListener("click", (event) => {
            event.preventDefault();
            toggleEmojiMenu();
        });
    }
    emojiButtons.forEach((button) => {
        button.addEventListener("click", () => {
            insertEmojiIntoMessage(button.dataset.insertEmoji || "🙂");
            closeEmojiMenu();
        });
    });
    document.addEventListener("click", (event) => {
        if (!emojiMenu || !emojiToggle) {
            return;
        }
        if (emojiMenu.contains(event.target) || emojiToggle.contains(event.target)) {
            return;
        }
        closeEmojiMenu();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeEmojiMenu();
        }
    });
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            markConversationRead();
        }
    });

    window.addEventListener("beforeunload", () => {
        clearImagePreviewUrl();
        clearVoicePreviewUrl();
    });
})();
