(function () {
    const toastArea = document.getElementById("live-toast-area");

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

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
    const notificationList = document.querySelector("[data-notification-list]");
    const notificationFeedUrl = notificationList
        ? notificationList.dataset.notificationFeedUrl || ""
        : "";
    const notificationEmptyText = notificationList
        ? notificationList.dataset.notificationEmptyText || "Brak powiadomień."
        : "Brak powiadomień.";

    let refreshInFlight = false;
    let notificationFeedInFlight = false;
    let previousState = null;

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

    function renderNotificationCard(item) {
        const line = `${escapeHtml(item.actorUsername)} ${escapeHtml(item.verb)}${
            item.locationLabel ? ` ${escapeHtml(item.locationLabel)}` : ""
        }`;
        const meta = [item.locationMeta, item.createdAt].filter(Boolean).join(" • ");

        return `
            <a class="notification-card ${item.isRead ? "" : "notification-card--new"}" href="${escapeHtml(item.openUrl)}">
                <div class="notification-card__icon"><i class="bi bi-bell-fill"></i></div>
                <div class="flex-grow-1">
                    <div class="notification-card__topline">
                        ${line}
                    </div>
                    <div class="notification-card__meta">
                        <span class="chat-room-badge">${escapeHtml(item.locationBadge || "Aktywność")}</span>
                        <span class="text-secondary small">${escapeHtml(meta)}</span>
                    </div>
                </div>
                ${item.isRead ? "" : '<span class="chat-room-badge">Nowe</span>'}
            </a>
        `;
    }

    function renderNotifications(items) {
        if (!notificationList) {
            return;
        }

        if (!items || !items.length) {
            notificationList.innerHTML = `<div class="empty-shell">${escapeHtml(notificationEmptyText)}</div>`;
            return;
        }

        notificationList.innerHTML = items.map(renderNotificationCard).join("");
    }

    function toastForUnreadNotifications(state) {
        if (!previousState || document.hidden) {
            return;
        }

        const seenIds = new Set(
            (previousState.latestUnreadNotifications || []).map((item) => String(item.id))
        );
        const newItems = (state.latestUnreadNotifications || []).filter(
            (item) => !seenIds.has(String(item.id))
        );

        if (!newItems.length) {
            return;
        }

        newItems.slice(0, 2).forEach((item) => {
            const title = item.threadId
                ? "Wiadomości prywatne"
                : item.channelId
                    ? "Nowa aktywność na kanale"
                    : "Powiadomienia";
            const body = `${item.actorUsername} ${item.verb}${
                item.locationLabel ? ` ${item.locationLabel}` : ""
            }`;
            window.discordToast(title, body);
        });

        if (newItems.length > 2) {
            window.discordToast("Powiadomienia", `Masz ${newItems.length} nowych zdarzeń.`);
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
        toastForUnreadNotifications(state);
        previousState = state;
    }

    async function refreshNotificationsFeed() {
        if (!notificationList || !notificationFeedUrl || notificationFeedInFlight) {
            return;
        }

        notificationFeedInFlight = true;
        try {
            const response = await fetch(notificationFeedUrl, {
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            if (!response.ok) {
                return;
            }

            const payload = await response.json();
            renderNotifications(payload.notifications || []);
        } catch (error) {
            console.debug("Notification feed refresh skipped", error);
        } finally {
            notificationFeedInFlight = false;
        }
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
            if (notificationList) {
                await refreshNotificationsFeed();
            }
        } catch (error) {
            console.debug("UI state refresh skipped", error);
        } finally {
            refreshInFlight = false;
        }
    }

    window.discordRefreshUiState = refreshUiState;
    window.discordRefreshNotifications = refreshNotificationsFeed;

    refreshUiState();
    window.setInterval(() => {
        if (!document.hidden) {
            refreshUiState();
        }
    }, 2500);

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            refreshUiState();
        }
    });
})();
