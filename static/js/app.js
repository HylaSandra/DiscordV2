(function () {
    const toastArea = document.getElementById("live-toast-area");
    if (!toastArea) {
        return;
    }

    window.discordToast = function discordToast(title, body) {
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
})();
