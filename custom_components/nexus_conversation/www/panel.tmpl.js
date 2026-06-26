(() => {
  const dashboardUrl = "__NEXUS_DASHBOARD_URL__";

  class NexusPanelElement extends HTMLElement {
    constructor() {
      super();
      this.hass = null;
    }

    set hass(hass) {
      this.hass = hass;
    }

    connectedCallback() {
      this.innerHTML = "";
      const container = document.createElement("div");
      container.style.cssText =
        "display:flex;width:100%;height:100%;margin:0;padding:0;overflow:hidden";

      if (dashboardUrl && dashboardUrl !== "{{SENTINEL}}") {
        const frame = document.createElement("iframe");
        frame.src = dashboardUrl;
        frame.style.cssText =
          "border:none;width:100%;height:100%;flex-grow:1";
        frame.allow = "fullscreen; clipboard-write; clipboard-read";
        frame.loading = "lazy";
        container.appendChild(frame);
      } else {
        const msg = document.createElement("div");
        msg.style.cssText =
          "display:flex;align-items:center;justify-content:center;height:100%;font-family:var(--primary-font-family);color:var(--secondary-text-color)";
        msg.textContent =
          "Configure the Nexus integration to launch the dashboard.";
        container.appendChild(msg);
      }

      this.appendChild(container);
    }
  }

  customElements.define("nexus-panel-element", NexusPanelElement);
})();
