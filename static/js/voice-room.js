(function () {
    const configNode = document.getElementById("voice-room-data");
    if (!configNode) {
        return;
    }

    const config = JSON.parse(configNode.textContent);
    const joinButton = document.getElementById("voice-join");
    const muteButton = document.getElementById("voice-mute");
    const leaveButton = document.getElementById("voice-leave");
    const statusNode = document.getElementById("voice-status");
    const participantsNode = document.getElementById("voice-participants");
    const remoteAudioHost = document.getElementById("remote-audio-host");

    const peers = new Map();
    const participants = new Map(
        (config.initialParticipants || []).map((user) => [user.id, user])
    );
    const moderatorIds = new Set(config.moderatorIds || []);
    const manuallyClosedSockets = new WeakSet();
    const SOCKET_KEEPALIVE_MS = 25000;
    const SOCKET_RECONNECT_BASE_MS = 1000;
    const SOCKET_RECONNECT_MAX_MS = 30000;
    let socket = null;
    let socketReady = null;
    let keepaliveTimer = null;
    let reconnectTimer = null;
    let reconnectAttempts = 0;
    let localStream = null;
    let muted = false;
    let hasJoined = false;

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value;
        return div.innerHTML;
    }

    function toast(title, body) {
        if (typeof window.discordToast === "function") {
            window.discordToast(title, body);
        }
    }

    function setStatus(text) {
        if (statusNode) {
            statusNode.textContent = text;
        }
    }

    function setIdleStatus() {
        setStatus(
            "Kliknij Dołącz do rozmowy, aby połączyć się z kanałem głosowym i zacząć rozmawiać."
        );
    }

    function describeMicrophoneError(error) {
        const errorName = error && error.name ? error.name : "";
        const errorMessage = error && error.message ? error.message : "";

        if (errorMessage === "socket_error") {
            return "Nie udało się połączyć z kanałem głosowym. Sprawdź połączenie WebSocket i konfigurację Render.";
        }

        if (!window.isSecureContext) {
            return "Kanał głosowy wymaga bezpiecznego połączenia HTTPS.";
        }

        if (window.top !== window.self) {
            return "Ta strona jest otwarta wewnątrz ramki. Otwórz aplikację bezpośrednio w przeglądarce i zezwól na mikrofon.";
        }

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            return "Twoja przeglądarka nie obsługuje dostępu do mikrofonu.";
        }

        if (errorName === "NotAllowedError" || errorName === "PermissionDeniedError") {
            return "Przeglądarka zablokowała dostęp do mikrofonu. Kliknij ikonę kłódki przy adresie strony i zezwól na mikrofon.";
        }

        if (errorName === "NotFoundError" || errorName === "DevicesNotFoundError") {
            return "Nie wykryto żadnego mikrofonu na tym urządzeniu.";
        }

        if (errorName === "NotReadableError" || errorName === "TrackStartError") {
            return "Nie udało się uruchomić mikrofonu. Sprawdź, czy nie korzysta z niego już inna aplikacja.";
        }

        if (errorName === "SecurityError" || errorName === "TypeError") {
            return "Przeglądarka nie pozwoliła uruchomić mikrofonu w tym kontekście strony.";
        }

        if (errorName === "AbortError") {
            return "Próba uruchomienia mikrofonu została przerwana. Spróbuj ponownie.";
        }

        return "Nie udało się uzyskać dostępu do mikrofonu.";
    }

    function orderedParticipants() {
        return Array.from(participants.values()).sort((left, right) => {
            const leftOwner = left.id === config.ownerId ? 0 : 1;
            const rightOwner = right.id === config.ownerId ? 0 : 1;
            if (leftOwner !== rightOwner) {
                return leftOwner - rightOwner;
            }

            const leftModerator = moderatorIds.has(left.id) ? 0 : 1;
            const rightModerator = moderatorIds.has(right.id) ? 0 : 1;
            if (leftModerator !== rightModerator) {
                return leftModerator - rightModerator;
            }

            return left.username.localeCompare(right.username, "pl");
        });
    }

    function renderParticipants() {
        if (!participantsNode) {
            return;
        }

        const html = orderedParticipants().map(
            (user) => `
            <div class="member-card">
                <div class="avatar-badge is-online">${
                    user.avatar_url
                        ? `<img src="${escapeHtml(user.avatar_url)}" alt="${escapeHtml(user.username)}">`
                        : `<span>${escapeHtml(user.username.charAt(0).toUpperCase())}</span>`
                }</div>
                <div class="flex-grow-1">
                    <div class="d-flex flex-wrap align-items-center gap-2">
                        <div class="fw-semibold">${escapeHtml(user.username)}</div>
                        ${user.id === config.ownerId ? '<span class="chat-room-badge">Właściciel</span>' : ""}
                        ${
                            user.id !== config.ownerId && moderatorIds.has(user.id)
                                ? '<span class="chat-room-badge">Moderator kanału</span>'
                                : ""
                        }
                    </div>
                    <div class="text-secondary small">${user.id === config.viewerId ? "Ty" : "Połączony(a)"}</div>
                </div>
            </div>
        `
        );

        participantsNode.innerHTML = html.length
            ? html.join("")
            : '<div class="empty-shell">Nikogo nie ma na kanale.</div>';
    }

    function send(data) {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(data));
        }
    }

    function stopKeepalive() {
        if (keepaliveTimer) {
            window.clearInterval(keepaliveTimer);
            keepaliveTimer = null;
        }
    }

    function startKeepalive() {
        stopKeepalive();
        send({ action: "ping" });
        keepaliveTimer = window.setInterval(() => {
            send({ action: "ping" });
        }, SOCKET_KEEPALIVE_MS);
    }

    function stopReconnect() {
        if (reconnectTimer) {
            window.clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    }

    function makeOffersToKnownParticipants() {
        participants.forEach((user, userId) => {
            if (userId !== config.viewerId) {
                makeOffer(user).catch((error) => {
                    console.error("Voice room renegotiation error:", error);
                });
            }
        });
    }

    function scheduleReconnect() {
        if (reconnectTimer) {
            return;
        }

        const delay = Math.min(
            SOCKET_RECONNECT_BASE_MS * 2 ** reconnectAttempts,
            SOCKET_RECONNECT_MAX_MS
        );
        reconnectAttempts += 1;
        reconnectTimer = window.setTimeout(async () => {
            reconnectTimer = null;
            try {
                await connectSocket();
                reconnectAttempts = 0;
                if (hasJoined) {
                    send({ action: "join-room" });
                    clearPeers();
                    makeOffersToKnownParticipants();
                    setStatus("Przywrocono polaczenie z kanalem glosowym.");
                } else {
                    setIdleStatus();
                }
            } catch (error) {
                scheduleReconnect();
            }
        }, delay);
    }

    function cleanupPeer(userId) {
        const peer = peers.get(userId);
        if (peer) {
            peer.close();
            peers.delete(userId);
        }

        const audio = document.getElementById(`remote-audio-${userId}`);
        if (audio) {
            audio.remove();
        }

        participants.delete(userId);
        renderParticipants();
    }

    function clearPeers() {
        peers.forEach((peer, userId) => {
            peer.close();
            const audio = document.getElementById(`remote-audio-${userId}`);
            if (audio) {
                audio.remove();
            }
        });
        peers.clear();
    }

    function attachRemoteStream(userId, stream) {
        if (!remoteAudioHost) {
            return;
        }

        let audio = document.getElementById(`remote-audio-${userId}`);
        if (!audio) {
            audio = document.createElement("audio");
            audio.id = `remote-audio-${userId}`;
            audio.autoplay = true;
            remoteAudioHost.appendChild(audio);
        }
        audio.srcObject = stream;
    }

    function createPeer(remoteUser) {
        if (!localStream) {
            return null;
        }

        if (peers.has(remoteUser.id)) {
            return peers.get(remoteUser.id);
        }

        const peer = new RTCPeerConnection({
            iceServers:
                Array.isArray(config.iceServers) && config.iceServers.length
                    ? config.iceServers
                    : [{ urls: "stun:stun.l.google.com:19302" }],
        });

        localStream.getTracks().forEach((track) => peer.addTrack(track, localStream));

        peer.onicecandidate = (event) => {
            if (event.candidate) {
                send({
                    action: "ice-candidate",
                    target: remoteUser.id,
                    data: event.candidate,
                });
            }
        };

        peer.ontrack = (event) => {
            attachRemoteStream(remoteUser.id, event.streams[0]);
        };

        peers.set(remoteUser.id, peer);
        return peer;
    }

    async function makeOffer(remoteUser) {
        const peer = createPeer(remoteUser);
        if (!peer) {
            return;
        }

        const offer = await peer.createOffer();
        await peer.setLocalDescription(offer);
        send({
            action: "offer",
            target: remoteUser.id,
            data: offer,
        });
    }

    function connectSocket() {
        if (socket && socket.readyState === WebSocket.OPEN) {
            return Promise.resolve();
        }

        if (socketReady) {
            return socketReady;
        }

        socketReady = new Promise((resolve, reject) => {
            const scheme = window.location.protocol === "https:" ? "wss" : "ws";
            const nextSocket = new WebSocket(
                `${scheme}://${window.location.host}${config.websocketPath}`
            );
            socket = nextSocket;

            nextSocket.addEventListener("open", () => {
                stopReconnect();
                reconnectAttempts = 0;
                startKeepalive();
                if (!hasJoined) {
                    setIdleStatus();
                }
                resolve();
            });

            nextSocket.addEventListener("message", async (event) => {
                const data = JSON.parse(event.data);
                const payload = data.payload || {};
                const remoteUser = payload.user || payload.from;

                if (
                    data.event === "membership_revoked" ||
                    data.event === "channel_banned"
                ) {
                    const actionText =
                        data.event === "channel_banned"
                            ? "zablokował(a) Cię na kanale"
                            : "usunął(ęła) Cię z kanału";
                    toast(
                        "Kanał",
                        `${payload.actorName} ${actionText} ${payload.channelName}.`
                    );
                    window.location.href = payload.redirectUrl || "/";
                    return;
                }

                if (data.event === "participant_joined" && remoteUser) {
                    participants.set(remoteUser.id, remoteUser);
                    renderParticipants();
                    if (hasJoined && remoteUser.id !== config.viewerId) {
                        send({
                            action: "presence-sync",
                            target: remoteUser.id,
                            data: {},
                        });
                        await makeOffer(remoteUser);
                    }
                    return;
                }

                if (
                    data.event === "presence-sync" &&
                    remoteUser &&
                    remoteUser.id !== config.viewerId
                ) {
                    participants.set(remoteUser.id, remoteUser);
                    renderParticipants();
                    return;
                }

                if (!hasJoined || !remoteUser || remoteUser.id === config.viewerId) {
                    if (data.event === "participant_left" && remoteUser) {
                        cleanupPeer(remoteUser.id);
                        toast(
                            "Kanał głosowy",
                            `${remoteUser.username} opuścił(a) rozmowę.`
                        );
                    }
                    return;
                }

                if (data.event === "offer") {
                    participants.set(remoteUser.id, remoteUser);
                    renderParticipants();
                    const peer = createPeer(remoteUser);
                    if (!peer) {
                        return;
                    }
                    await peer.setRemoteDescription(
                        new RTCSessionDescription(payload.data)
                    );
                    const answer = await peer.createAnswer();
                    await peer.setLocalDescription(answer);
                    send({
                        action: "answer",
                        target: remoteUser.id,
                        data: answer,
                    });
                    return;
                }

                if (data.event === "answer") {
                    const peer = peers.get(remoteUser.id);
                    if (peer) {
                        await peer.setRemoteDescription(
                            new RTCSessionDescription(payload.data)
                        );
                    }
                    return;
                }

                if (data.event === "ice-candidate") {
                    const peer = peers.get(remoteUser.id) || createPeer(remoteUser);
                    if (peer) {
                        await peer.addIceCandidate(new RTCIceCandidate(payload.data));
                    }
                    return;
                }

                if (data.event === "participant_left") {
                    cleanupPeer(remoteUser.id);
                    toast(
                        "Kanał głosowy",
                        `${remoteUser.username} opuścił(a) rozmowę.`
                    );
                }
            });

            nextSocket.addEventListener("close", () => {
                stopKeepalive();
                if (socket === nextSocket) {
                    socket = null;
                    socketReady = null;
                }
                if (manuallyClosedSockets.has(nextSocket)) {
                    return;
                }
                setStatus(
                    hasJoined
                        ? "Połączenie z kanałem zostało zamknięte."
                        : "Podgląd kanału głosowego został zamknięty."
                );
                scheduleReconnect();
            });

            nextSocket.addEventListener(
                "error",
                () => {
                    reject(new Error("socket_error"));
                },
                { once: true }
            );
        });

        return socketReady;
    }

    async function joinVoiceSession() {
        if (hasJoined || localStream) {
            return;
        }

        try {
            await connectSocket();
            localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            hasJoined = true;
            send({ action: "join-room" });
            participants.set(config.viewerId, {
                id: config.viewerId,
                username: config.viewerName || "Ty",
                avatar_url: config.viewerAvatar || "",
            });
            renderParticipants();
            joinButton.disabled = true;
            muteButton.disabled = false;
            leaveButton.disabled = false;
            setStatus("Połączono z kanałem głosowym.");
        } catch (error) {
            const details = describeMicrophoneError(error);
            console.error("Voice room microphone error:", error);
            setStatus(details);
            toast("Kanał głosowy", details);
        }
    }

    function leaveVoice() {
        stopReconnect();
        stopKeepalive();
        clearPeers();
        participants.delete(config.viewerId);
        renderParticipants();

        if (localStream) {
            localStream.getTracks().forEach((track) => track.stop());
            localStream = null;
        }

        if (socket) {
            const closingSocket = socket;
            manuallyClosedSockets.add(closingSocket);
            socket = null;
            socketReady = null;
            closingSocket.close();
        }

        hasJoined = false;
        joinButton.disabled = false;
        muteButton.disabled = true;
        leaveButton.disabled = true;
        muted = false;
        muteButton.textContent = "Wycisz mikrofon";
        setStatus("Rozłączono z kanałem głosowym.");

        connectSocket().catch(() => {
            setStatus("Nie udało się przywrócić podglądu kanału głosowego.");
        });
    }

    function toggleMute() {
        if (!localStream) {
            return;
        }

        muted = !muted;
        localStream.getAudioTracks().forEach((track) => {
            track.enabled = !muted;
        });
        muteButton.textContent = muted ? "Włącz mikrofon" : "Wycisz mikrofon";
        setStatus(muted ? "Mikrofon jest wyciszony." : "Mikrofon jest aktywny.");
    }

    renderParticipants();
    connectSocket().catch(() => {
        setStatus("Nie udało się połączyć z kanałem głosowym.");
    });

    if (joinButton) {
        joinButton.addEventListener("click", joinVoiceSession);
    }
    if (leaveButton) {
        leaveButton.addEventListener("click", leaveVoice);
    }
    if (muteButton) {
        muteButton.addEventListener("click", toggleMute);
    }
})();
