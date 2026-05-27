(function () {
    const toastArea = document.getElementById("live-toast-area");

    window.discordToast = function discordToast(title, body) {
        if (!toastArea) {
            return;
        }

        const toast = document.createElement("div");
        toast.className = "live-toast";

        const titleNode = document.createElement("strong");
        titleNode.className = "d-block mb-1";
        titleNode.textContent = title;

        const bodyNode = document.createElement("span");
        bodyNode.className = "text-secondary";
        bodyNode.textContent = body;

        toast.appendChild(titleNode);
        toast.appendChild(bodyNode);
        toastArea.appendChild(toast);

        window.setTimeout(() => {
            toast.remove();
        }, 4200);
    };

    const isAuthenticated = document.body.dataset.authenticated === "true";
    const uiStateUrl = document.body.dataset.uiStateUrl || "";

    if (!isAuthenticated || !uiStateUrl) {
        return;
    }

    const notificationPill = document.querySelector("[data-notification-pill]");
    const currentUserAvatar = document.querySelector("[data-current-user-avatar]");
    const currentUserStatusValue = document.querySelector("[data-user-status-value]");
    const currentUserVoiceLine = document.querySelector("[data-user-voice-line]");
    const currentUserVoiceText = document.querySelector("[data-user-voice-text]");
    let refreshInFlight = false;

    function setUnreadState(selector, ids, activeClass) {
        const idSet = new Set((ids || []).map((value) => String(value)));

        document.querySelectorAll(selector).forEach((node) => {
            const targetId = node.dataset.navChannelId || node.dataset.navThreadId;
            const isUnread = idSet.has(String(targetId));
            node.classList.toggle(activeClass, isUnread);
        });
    }

    function setUnreadDots(selector, ids) {
        const idSet = new Set((ids || []).map((value) => String(value)));

        document.querySelectorAll(selector).forEach((node) => {
            const targetId = node.dataset.unreadChannelDot || node.dataset.unreadThreadDot;
            node.classList.toggle("d-none", !idSet.has(String(targetId)));
        });
    }

    function setVoiceChannelPills(voiceChannels) {
        const counts = new Map(
            (voiceChannels || []).map((row) => [String(row.id), Number(row.activeCount || 0)])
        );

        document.querySelectorAll("[data-voice-channel-pill]").forEach((node) => {
            const channelId = String(node.dataset.voiceChannelPill);
            const count = counts.get(channelId) || 0;

            if (count > 0) {
                node.classList.remove("d-none");
                node.textContent = count > 1 ? `Na żywo · ${count}` : "Na żywo";
            } else {
                node.classList.add("d-none");
                node.textContent = "";
            }
        });
    }

    function setUserPresence(state) {
        if (currentUserStatusValue) {
            currentUserStatusValue.textContent = state.effectiveStatus || "offline";
        }

        if (currentUserAvatar) {
            const isOnline = state.effectiveStatus === "online";
            currentUserAvatar.classList.toggle("is-online", isOnline);
            currentUserAvatar.classList.toggle("is-offline", !isOnline);
        }

        if (!currentUserVoiceLine || !currentUserVoiceText) {
            return;
        }

        if (state.activeVoiceChannel && state.activeVoiceChannel.presenceText) {
            currentUserVoiceLine.classList.remove("d-none");
            currentUserVoiceText.textContent = state.activeVoiceChannel.presenceText;
        } else {
            currentUserVoiceLine.classList.add("d-none");
            currentUserVoiceText.textContent = "";
        }
    }

    function applyUiState(state) {
        if (notificationPill) {
            const unreadCount = Number(state.unreadNotificationsCount || 0);
            notificationPill.textContent = unreadCount;
            notificationPill.classList.toggle("d-none", unreadCount === 0);
        }

        setUnreadState("[data-nav-channel-id]", state.unreadChannelIds, "stack-link--unread");
        setUnreadDots("[data-unread-channel-dot]", state.unreadChannelIds);
        setUnreadState("[data-nav-thread-id]", state.unreadThreadIds, "stack-link--unread");
        setUnreadDots("[data-unread-thread-dot]", state.unreadThreadIds);
        setVoiceChannelPills(state.voiceChannels);
        setUserPresence(state);
    }

    async function refreshUiState() {
        if (refreshInFlight) {
            return;
        }

        refreshInFlight = true;
        try {
            const response = await fetch(uiStateUrl, {
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            if (!response.ok) {
                return;
            }

            const state = await response.json();
            applyUiState(state);
        } catch (error) {
            console.debug("UI state refresh skipped", error);
        } finally {
            refreshInFlight = false;
        }
    }

    window.discordRefreshUiState = refreshUiState;

    refreshUiState();
    window.setInterval(() => {
        if (!document.hidden) {
            refreshUiState();
        }
    }, 4000);

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            refreshUiState();
        }
    });
})();
